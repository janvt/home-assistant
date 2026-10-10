"""mux7seg — software-multiplexed 7-segment display, driven by a hardware timer ISR.

Hardware model (see the kitchen-timer driver board):
  * 8 segment lines (A B C D E F G DP), GPIO high = segment sinks current (NPN on)
  * N digit lines (common anodes), GPIO high = digit powered (NPN level shifter -> PNP on)
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.components.esp32 import add_idf_sdkconfig_option
from esphome.const import CONF_BRIGHTNESS, CONF_ID, CONF_LAMBDA

mux7seg_ns = cg.esphome_ns.namespace("mux7seg")
Mux7Seg = mux7seg_ns.class_("Mux7Seg", cg.PollingComponent)
Mux7SegRef = Mux7Seg.operator("ref")

CONF_SEGMENT_PINS = "segment_pins"
CONF_DIGIT_PINS = "digit_pins"
CONF_SLOT_TIME = "slot_time"
CONF_BLANK_TIME = "blank_time"


def _validate_pins(config):
    all_pins = config[CONF_SEGMENT_PINS] + config[CONF_DIGIT_PINS]
    if len(set(all_pins)) != len(all_pins):
        raise cv.Invalid("Each GPIO may only be used once across segment_pins and digit_pins")
    if max(all_pins) > 31:
        # The ISR switches everything with single writes to GPIO_OUT_W1TS/W1TC,
        # which only cover GPIO0-31.
        raise cv.Invalid("All display pins must be GPIO0-31 (one register covers them)")
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(Mux7Seg),
            # Order matters: A, B, C, D, E, F, G, DP
            cv.Required(CONF_SEGMENT_PINS): cv.All(
                cv.ensure_list(pins.internal_gpio_output_pin_number),
                cv.Length(min=8, max=8),
            ),
            # Left to right
            cv.Required(CONF_DIGIT_PINS): cv.All(
                cv.ensure_list(pins.internal_gpio_output_pin_number),
                cv.Length(min=1, max=8),
            ),
            # Time each digit owns per scan cycle. 1 ms x 4 digits = 250 Hz per digit.
            cv.Optional(CONF_SLOT_TIME, default="1ms"): cv.All(
                cv.positive_time_period_microseconds,
                cv.Range(
                    min=cv.TimePeriod(microseconds=200),
                    max=cv.TimePeriod(microseconds=5000),
                ),
            ),
            # Dark gap between digits so the previous PNP's stored base charge can drain.
            cv.Optional(CONF_BLANK_TIME, default="5us"): cv.All(
                cv.positive_time_period_microseconds,
                cv.Range(max=cv.TimePeriod(microseconds=50)),
            ),
            cv.Optional(CONF_BRIGHTNESS, default=1.0): cv.percentage,
            cv.Optional(CONF_LAMBDA): cv.lambda_,
        }
    ).extend(cv.polling_component_schema("100ms")),
    cv.only_on_esp32,
    _validate_pins,
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_segment_pins(config[CONF_SEGMENT_PINS]))
    cg.add(var.set_digit_pins(config[CONF_DIGIT_PINS]))
    cg.add(var.set_slot_us(config[CONF_SLOT_TIME].total_microseconds))
    cg.add(var.set_blank_us(config[CONF_BLANK_TIME].total_microseconds))
    cg.add(var.set_brightness(config[CONF_BRIGHTNESS]))

    if CONF_LAMBDA in config:
        lambda_ = await cg.process_lambda(
            config[CONF_LAMBDA], [(Mux7SegRef, "it")], return_type=cg.void
        )
        cg.add(var.set_writer(lambda_))

    # Keep the timer ISR and the alarm-reprogramming call in IRAM, so the scan keeps
    # running while flash is busy (OTA updates, NVS writes). Without this, the flash
    # cache is disabled during writes, the ISR can't execute, and one digit freezes on.
    add_idf_sdkconfig_option("CONFIG_GPTIMER_ISR_IRAM_SAFE", True)
    add_idf_sdkconfig_option("CONFIG_GPTIMER_CTRL_FUNC_IN_IRAM", True)
