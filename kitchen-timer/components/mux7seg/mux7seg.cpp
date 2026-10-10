#include "mux7seg.h"

#include <cstdarg>
#include <cstdio>

#include "driver/gpio.h"
#include "driver/gptimer.h"
#include "esp_attr.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "soc/gpio_reg.h"
#include "esphome/core/log.h"

namespace esphome {
namespace mux7seg {

static const char *const TAG = "mux7seg";

// ---------------------------------------------------------------------------
// State shared with the ISR.
//
// DRAM_ATTR pins these into internal RAM. The ISR is in IRAM and must never touch
// flash-mapped memory: while flash is being written (OTA, NVS), the cache is off and
// any such access would crash. Component members live on the heap, which on a PSRAM
// board might not be internal, so the ISR only ever reads these statics.
// ---------------------------------------------------------------------------
static DRAM_ATTR volatile uint32_t s_seg_mask[MAX_DIGITS];  // which segment GPIOs to raise, per digit
static DRAM_ATTR uint32_t s_digit_mask[MAX_DIGITS];         // the one digit GPIO, per digit
static DRAM_ATTR uint32_t s_all_mask = 0;                   // every display GPIO
static DRAM_ATTR uint8_t s_num_digits = 0;
static DRAM_ATTR uint32_t s_blank_us = 5;
static DRAM_ATTR volatile uint32_t s_on_us = 1000;   // alarm length of the lit phase
static DRAM_ATTR volatile uint32_t s_off_us = 0;     // alarm length of the dark phase (0 = full brightness)
static DRAM_ATTR uint8_t s_digit = 0;
static DRAM_ATTR bool s_lit = false;
static DRAM_ATTR volatile uint32_t s_scans = 0;      // heartbeat, read by update()

// Timer alarm: one call per phase. Each digit's slot is
//   [ blank | segments + digit on ..... ][ all off ...... ]
//   |<------------- s_on_us ----------->|<-- s_off_us -->|
// The timer auto-reloads to 0 on each alarm, and we reprogram the next alarm length here.
static bool IRAM_ATTR on_alarm(gptimer_handle_t timer, const gptimer_alarm_event_data_t *edata,
                               void *user_ctx) {
  uint32_t next_us;

  if (!s_lit || s_off_us == 0) {
    // Start the next digit.
    s_digit = (s_digit + 1 < s_num_digits) ? s_digit + 1 : 0;

    // 1. Everything off. One register write: all bits in the mask go low at the same instant.
    REG_WRITE(GPIO_OUT_W1TC_REG, s_all_mask);
    // 2. Anti-ghosting gap: the previous PNP keeps conducting until its stored base charge
    //    drains (storage time). Busy-wait is fine here: ROM function, a few microseconds.
    esp_rom_delay_us(s_blank_us);
    // 3. Segments for this digit, then the digit itself.
    REG_WRITE(GPIO_OUT_W1TS_REG, s_seg_mask[s_digit]);
    REG_WRITE(GPIO_OUT_W1TS_REG, s_digit_mask[s_digit]);

    s_lit = true;
    s_scans = s_scans + 1;  // only the ISR writes this; a single aligned 32-bit store
    next_us = s_on_us;
  } else {
    // Dimming: switch the digit off early and stay dark for the rest of the slot.
    REG_WRITE(GPIO_OUT_W1TC_REG, s_all_mask);
    s_lit = false;
    next_us = s_off_us;
  }

  gptimer_alarm_config_t alarm = {};
  alarm.alarm_count = next_us;  // timer runs at 1 MHz, so counts == microseconds
  alarm.reload_count = 0;
  alarm.flags.auto_reload_on_alarm = true;
  gptimer_set_alarm_action(timer, &alarm);  // IRAM-safe thanks to CONFIG_GPTIMER_CTRL_FUNC_IN_IRAM

  return false;  // no higher-priority task was woken
}

static void timer_task(void *arg) {
  static_cast<Mux7Seg *>(arg)->start_timer_();
  vTaskDelete(nullptr);
}

// ---------------------------------------------------------------------------

void Mux7Seg::setup() {
  uint64_t pin_mask = 0;
  s_all_mask = 0;
  for (auto pin : this->segment_pins_)
    s_all_mask |= 1UL << pin;
  for (auto pin : this->digit_pins_)
    s_all_mask |= 1UL << pin;
  pin_mask = s_all_mask;

  // Outputs low before anything else: every transistor stays off.
  REG_WRITE(GPIO_OUT_W1TC_REG, s_all_mask);
  gpio_config_t io = {};
  io.pin_bit_mask = pin_mask;
  io.mode = GPIO_MODE_OUTPUT;
  io.pull_up_en = GPIO_PULLUP_DISABLE;
  io.pull_down_en = GPIO_PULLDOWN_DISABLE;
  io.intr_type = GPIO_INTR_DISABLE;
  gpio_config(&io);

  s_num_digits = this->digit_pins_.size();
  for (uint8_t d = 0; d < s_num_digits; d++) {
    s_digit_mask[d] = 1UL << this->digit_pins_[d];
    s_seg_mask[d] = 0;
  }
  s_blank_us = this->blank_us_;
  this->set_brightness(this->brightness_);

  // The ISR's interrupt is allocated on the core that installs it. Do that from a short-lived
  // task pinned to the last core (core 1 on the S3), away from the Wi-Fi stack on core 0.
  const BaseType_t core = portNUM_PROCESSORS - 1;
  if (xTaskCreatePinnedToCore(timer_task, "mux7seg", 4096, this, 5, nullptr, core) != pdPASS) {
    ESP_LOGE(TAG, "Could not create timer task");
    this->mark_failed();
  }
}

void Mux7Seg::start_timer_() {
  gptimer_handle_t timer = nullptr;

  gptimer_config_t cfg = {};
  cfg.clk_src = GPTIMER_CLK_SRC_DEFAULT;
  cfg.direction = GPTIMER_COUNT_UP;
  cfg.resolution_hz = 1000000;  // 1 tick = 1 us
  ESP_ERROR_CHECK(gptimer_new_timer(&cfg, &timer));

  gptimer_event_callbacks_t cbs = {};
  cbs.on_alarm = on_alarm;
  ESP_ERROR_CHECK(gptimer_register_event_callbacks(timer, &cbs, nullptr));

  gptimer_alarm_config_t alarm = {};
  alarm.alarm_count = this->slot_us_;
  alarm.reload_count = 0;
  alarm.flags.auto_reload_on_alarm = true;
  ESP_ERROR_CHECK(gptimer_set_alarm_action(timer, &alarm));

  ESP_ERROR_CHECK(gptimer_enable(timer));
  ESP_ERROR_CHECK(gptimer_start(timer));
  this->last_scans_ = s_scans;
  this->timer_started_ = true;
  ESP_LOGD(TAG, "Scan timer running on core %d", xPortGetCoreID());
}

void Mux7Seg::set_brightness(float brightness) {
  if (brightness > 1.0f)
    brightness = 1.0f;
  if (brightness < 0.02f)
    brightness = 0.02f;
  this->brightness_ = brightness;

  // On-time includes the blank gap; keep at least 10 us of actual light.
  uint32_t on = this->blank_us_ + (uint32_t) ((this->slot_us_ - this->blank_us_) * brightness);
  if (on < this->blank_us_ + 10)
    on = this->blank_us_ + 10;
  if (on > this->slot_us_)
    on = this->slot_us_;

  // Two separate writes; the ISR may see one new and one old value for a single slot.
  // That's one 1 ms slot slightly off, invisible.
  s_off_us = this->slot_us_ - on;
  s_on_us = on;
}

void Mux7Seg::update() {
  // Heartbeat check. At 1 ms per digit, ~50 scans happen between two updates;
  // an unchanged count means the ISR has stopped and one digit is stuck at 100%.
  if (this->timer_started_) {
    const uint32_t scans = s_scans;
    if (scans == this->last_scans_) {
      REG_WRITE(GPIO_OUT_W1TC_REG, s_all_mask);  // blank everything, keep it blank
      if (!this->stalled_) {
        ESP_LOGE(TAG, "Scan ISR stopped: display blanked");
        this->status_set_error();
        this->stalled_ = true;
      }
    } else if (this->stalled_) {
      ESP_LOGW(TAG, "Scan ISR running again");
      this->status_clear_error();
      this->stalled_ = false;
    }
    this->last_scans_ = scans;
  }

  if (this->writer_.has_value()) {
    this->clear();
    (*this->writer_)(*this);
  }
  this->commit_();
}

void Mux7Seg::commit_() {
  for (uint8_t d = 0; d < s_num_digits; d++) {
    uint32_t mask = 0;
    for (uint8_t bit = 0; bit < 8; bit++) {
      if (this->buffer_[d] & (1 << bit))
        mask |= 1UL << this->segment_pins_[bit];
    }
    s_seg_mask[d] = mask;  // single 32-bit store: the ISR never sees a half-written mask
  }
}

void Mux7Seg::dump_config() {
  ESP_LOGCONFIG(TAG, "Multiplexed 7-segment display:");
  ESP_LOGCONFIG(TAG, "  Digits: %u", (unsigned) this->digit_pins_.size());
  ESP_LOGCONFIG(TAG, "  Slot: %u us (%u Hz per digit), blank: %u us", (unsigned) this->slot_us_,
                (unsigned) (1000000 / (this->slot_us_ * this->digit_pins_.size())), (unsigned) this->blank_us_);
  ESP_LOGCONFIG(TAG, "  Brightness: %.0f%%", this->brightness_ * 100.0f);
  LOG_UPDATE_INTERVAL(this);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

void Mux7Seg::clear() {
  for (auto &b : this->buffer_)
    b = 0;
}

void Mux7Seg::set_raw(uint8_t digit, uint8_t segments) {
  if (digit < this->digit_pins_.size())
    this->buffer_[digit] = segments;
}

uint8_t Mux7Seg::print(uint8_t start, const char *str) {
  const uint8_t n = this->digit_pins_.size();
  uint8_t pos = start;
  for (; *str != '\0'; str++) {
    if (*str == '.') {
      if (pos > start) {
        this->buffer_[pos - 1] |= 0x80;  // attach to previous character
        continue;
      }
      if (pos < n)
        this->buffer_[pos++] = 0x80;  // leading dot gets its own digit
      continue;
    }
    if (pos >= n)
      break;
    this->buffer_[pos++] = encode_(*str);
  }
  return pos - start;
}

uint8_t Mux7Seg::printf(uint8_t start, const char *format, ...) {
  char buf[32];
  va_list arg;
  va_start(arg, format);
  vsnprintf(buf, sizeof(buf), format, arg);
  va_end(arg);
  return this->print(start, buf);
}

uint8_t Mux7Seg::printf(const char *format, ...) {
  char buf[32];
  va_list arg;
  va_start(arg, format);
  vsnprintf(buf, sizeof(buf), format, arg);
  va_end(arg);
  return this->print(0, buf);
}

//      A
//     ---
//  F |   | B       bit: 0=A 1=B 2=C 3=D 4=E 5=F 6=G 7=DP
//     -G-
//  E |   | C
//     ---  .DP
//      D
uint8_t Mux7Seg::encode_(char c) {
  switch (c) {
    case '0': case 'O': return 0x3F;
    case '1': return 0x06;
    case '2': return 0x5B;
    case '3': return 0x4F;
    case '4': return 0x66;
    case '5': case 'S': case 's': return 0x6D;
    case '6': return 0x7D;
    case '7': return 0x07;
    case '8': return 0x7F;
    case '9': return 0x6F;
    case 'A': case 'a': return 0x77;
    case 'b': case 'B': return 0x7C;
    case 'C': return 0x39;
    case 'c': return 0x58;
    case 'd': case 'D': return 0x5E;
    case 'E': case 'e': return 0x79;
    case 'F': case 'f': return 0x71;
    case 'G': case 'g': return 0x3D;
    case 'H': return 0x76;
    case 'h': return 0x74;
    case 'I': case 'i': return 0x30;
    case 'J': case 'j': return 0x1E;
    case 'L': case 'l': return 0x38;
    case 'n': case 'N': return 0x54;
    case 'o': return 0x5C;
    case 'P': case 'p': return 0x73;
    case 'r': case 'R': return 0x50;
    case 't': case 'T': return 0x78;
    case 'U': return 0x3E;
    case 'u': return 0x1C;
    case 'y': case 'Y': return 0x6E;
    case '-': return 0x40;
    case '_': return 0x08;
    default: return 0x00;  // space and anything unknown
  }
}

}  // namespace mux7seg
}  // namespace esphome
