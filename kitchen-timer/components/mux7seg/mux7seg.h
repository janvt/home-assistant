#pragma once

#include <cstdint>
#include <functional>
#include <vector>

#include "esphome/core/component.h"

namespace esphome {
namespace mux7seg {

static constexpr uint8_t MAX_DIGITS = 8;

class Mux7Seg;
using mux7seg_writer_t = std::function<void(Mux7Seg &)>;

class Mux7Seg : public PollingComponent {
 public:
  // --- configuration (called from generated code) ---
  void set_segment_pins(const std::vector<uint8_t> &pins) { this->segment_pins_ = pins; }
  void set_digit_pins(const std::vector<uint8_t> &pins) { this->digit_pins_ = pins; }
  void set_slot_us(uint32_t us) { this->slot_us_ = us; }
  void set_blank_us(uint32_t us) { this->blank_us_ = us; }
  void set_writer(mux7seg_writer_t &&writer) { this->writer_ = writer; }

  // 0.0-1.0. Implemented as on-time within each digit's slot (PWM inside the scan).
  // Safe to call at runtime, e.g. from a template number.
  void set_brightness(float brightness);

  // --- component lifecycle ---
  void setup() override;
  void update() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::PROCESSOR; }

  // --- rendering API, used inside the YAML lambda as `it.` ---
  // A '.' lights the decimal point of the preceding character instead of taking a digit.
  uint8_t print(uint8_t start, const char *str);
  uint8_t print(const char *str) { return this->print(0, str); }
  uint8_t printf(uint8_t start, const char *format, ...) __attribute__((format(printf, 3, 4)));
  uint8_t printf(const char *format, ...) __attribute__((format(printf, 2, 3)));
  // Raw segment byte: bit0 = A ... bit6 = G, bit7 = DP
  void set_raw(uint8_t digit, uint8_t segments);
  void clear();

  // Runs inside a FreeRTOS task pinned to the last core; public only for that trampoline.
  void start_timer_();

 protected:
  void commit_();  // translate buffer_ -> GPIO masks the ISR reads
  static uint8_t encode_(char c);

  std::vector<uint8_t> segment_pins_;
  std::vector<uint8_t> digit_pins_;
  uint32_t slot_us_{1000};
  uint32_t blank_us_{5};
  float brightness_{1.0f};
  uint8_t buffer_[MAX_DIGITS]{};
  optional<mux7seg_writer_t> writer_{};

  // Scan heartbeat: the ISR counts completed digit switches; update() checks the
  // count moved. If it didn't, the scan is dead and one digit would be stuck on,
  // so the display is blanked and the component reports an error instead.
  volatile bool timer_started_{false};  // set from the timer task on the other core
  uint32_t last_scans_{0};
  bool stalled_{false};
};

}  // namespace mux7seg
}  // namespace esphome
