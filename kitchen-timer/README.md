# Kitchen timer

A wall-mounted kitchen timer: turn a knob to set the time, press to start, and
four big red 7-segment digits count down, readable from across the kitchen.
The timer itself lives in Home Assistant, so it also shows up on the phone and
survives reboots of either side.

**Status: designed, not built.** The firmware has never been compiled or run on
hardware. `esphome config` validation runs in CI; the C++ parsing helpers are
compiled and tested on the host. Expect a first-compile fix or two in
`components/mux7seg/`.

| File | What it is |
|------|------------|
| [`kitchen-timer.yaml`](kitchen-timer.yaml) | ESPHome config: knob, button, buzzer, and the HA-owned timer logic. |
| [`components/mux7seg/`](components/mux7seg/) | Custom ESPHome component: software-multiplexed 7-segment display driven from a hardware-timer ISR. |
| [`kitchen_timer_helpers.h`](kitchen_timer_helpers.h) | Pure C++: parses HA's `finishes_at` / `remaining`. Tested by [`tests/test_helpers.cpp`](tests/test_helpers.cpp). |
| [`../automations/kitchen_timer_finished.yaml`](../automations/kitchen_timer_finished.yaml) | Phone notification when the timer runs out. |

## How it works

```
knob + button ──timer.start / pause / cancel──▶ timer.kitchen (Home Assistant)
display       ◀──state, finishes_at, remaining──┘        │
buzzer        ◀── cached deadline (local)                 └─timer.finished─▶ iPhone
```

- **Home Assistant owns the timer.** The device is a thin client: it sends
  actions and mirrors state. A `timer` helper with *restore* survives a restart
  of HA and of the device; a reboot mid-cooking just picks the countdown back up.
- **The countdown is computed on the device** from HA's absolute `finishes_at`
  and the HA-synced clock. HA's `remaining` attribute does **not** tick while a
  timer runs; it is only accurate while paused, which is the only time it is used.
- **The deadline is cached.** If Wi-Fi or HA drop mid-cooking, the display keeps
  counting and the buzzer still rings at zero.
- **Presses are optimistic.** The display changes immediately; if HA hasn't
  confirmed within 3 s, the device falls back to HA's last known state.

| Input | Idle | Running | Paused | Ringing |
|-------|------|---------|--------|---------|
| Turn knob | set time (10 s steps to 2 min, 30 s to 10 min, then 1 min) | — | — | — |
| Short press | start | pause | resume | silence |
| Long press (≥ 1 s) | — | cancel | cancel | silence |

Without a connection to HA, only the knob and silencing work. Start, pause and
cancel are refused (`----` and a double beep) so HA stays the single source of
truth. The display: blinking dot = running, steady dot = paused, flashing
`0.00` = ringing, `--.--` = running but the clock hasn't synced yet.

## Home Assistant setup

1. **Timer helper** `timer.kitchen`: Settings → Devices & services → Helpers →
   Create helper → Timer, with *Restore* enabled. Or in YAML:
   ```yaml
   timer:
     kitchen:
       name: Kitchen
       restore: true
   ```
2. **Allow actions:** in the ESPHome integration, open the device's options and
   enable *Allow the device to perform Home Assistant actions*. Without it the
   knob and display work but every press is silently dropped by HA.
3. **Automation:** paste [`kitchen_timer_finished.yaml`](../automations/kitchen_timer_finished.yaml).
   It sends an iOS *time-sensitive* notification, which breaks through Focus modes.
4. **Secrets:** add to `secrets.yaml` next to the config (git-ignored):
   `kitchentimerencryption` (32 random bytes, base64: `openssl rand -base64 32`),
   plus the usual `wifi_ssid` / `wifi_password`.

## Hardware

Two boards joined by a 12-wire ribbon:

- **Display board:** passive. Four socketed Lite-On LTS-3401 digits (0.8",
  common anode, red) and eight bus rails, nothing else. Sits flush behind a red
  or smoked acrylic front, which makes unlit segments nearly invisible.
- **Driver board:** ESP32-S3 dev board (socketed), 4 digit switches, 8 segment
  sinks, bulk capacitance, encoder and buzzer headers, USB power.

### Pin map (ESP32-S3)

| Function | GPIO |
|----------|------|
| Segments A B C D E F G DP | 4 5 6 7 8 9 10 11 |
| Digits 1–4 (left to right) | 12 13 14 15 |
| Encoder A / B / push | 16 / 17 / 18 |
| Buzzer | 21 |

All display pins are below 32, so one register write switches all twelve at
once. Avoided: strapping pins (0, 3, 45, 46), USB (19, 20), UART0 (43, 44),
flash/PSRAM (26–37 on octal-PSRAM boards).

### Circuits

**Digit switch, ×4.** A PNP transistor sources 5 V into the
digit's common anode. A 3.3 V GPIO can't turn a PNP *off* when its emitter sits
at 5 V (V_EB would still be 1.7 V), so an NPN level shifter drives its base:

```
GPIO ─[2.2k]─┬─ NPN base            5V ──┬───────── PNP emitter
          [10k]   NPN emitter ─ GND    [10k]
           GND    NPN collector ─[470Ω]─┴─ PNP base
                                           PNP collector ─ anode pins 4, 6, 12, 17
```

**Segment sink, ×8.** `GPIO ─[1k]─ NPN base`, emitter to GND, collector
`─[150Ω]─` segment bus. No base pull-down needed: a segment can only light when
a digit is powered, and the digit switches are held off by their pull-downs
while the GPIOs float during boot.

**Power:** 220 µF + 100 nF across 5 V, next to the PNP emitters. Wi-Fi transmit
bursts (~300 mA) on top of a lit `88.88` (~140 mA) through a thin USB cable is
the brownout scenario this covers.

### The numbers

- **Segment current:** (5 − 0.2 PNP sat − ~2.2 Vf − 0.1 NPN sat) / 150 Ω ≈ 17 mA
  peak; across the Vf spread (2.0–2.6 V) 15–18 mA. 150 Ω because the resistor
  set on hand has no 120 Ω.
- **Average** at ¼ duty: ~4 mA per segment. Bright enough indoors.
- **Hang safety:** if the scan stops, one digit stays on at ≤ 18 mA per segment,
  under the LTS-3401's 25 mA continuous rating. A crash looks bad but damages
  nothing. On top of that, the component blanks the display when its heartbeat
  stops (see below).
- **Digit switch:** up to 8 × 17 ≈ 136 mA. PNP base current (5 − 0.7 − 0.1) /
  470 Ω ≈ 9 mA, forced β ≈ 15: firmly saturated.
- **5 V rail:** ~140 mA display + 50–100 mA ESP average. About 1 W from USB.

### LTS-3401 pinout

From the sibling LTS-3401AE/LE datasheets (red-orange GaAsP, gray face, white
segments, left and right DP). The parts on hand are marked LTS3401VWE, a
variant with no datasheet found. The package matches: 13 pins on an 18-position
2 × 9 grid, two DP dots. Map one digit in diode mode before soldering anything.

| Pin | Function |
|-----|----------|
| 4, 6, 12, 17 | common anode (tied internally) |
| 2, 15, 13, 11, 5, 3, 14 | segments A, B, C, D, E, F, G |
| 7 / 10 | left / right decimal point |
| 1, 8, 9, 16, 18 | not connected |

The DP rail connects every digit's right DP (pin 10); the firmware decides
which one lights, e.g. digit 2's as the minutes/seconds separator.

### Parts

| Part | Notes |
|------|-------|
| 4 × LTS-3401 | on hand |
| [Waveshare ESP32-S3 dev board](https://www.bastelgarage.ch/esp8266-esp32/esp-boards/waveshare-esp32-s3-entwicklungsboard) | dual core: the scan ISR gets core 1 to itself |
| 4 × PNP, ≥ 300 mA | BC327, S8550, 2N4403 or BC640. **Not** 2N3906 (200 mA, gain drops). |
| 12 × small NPN | 2N3904, BC547, BC337 or S8050 |
| Resistors | 8 × 150 Ω, 8 × 1 kΩ, 4 × 2.2 kΩ, 4 × 470 Ω, 8 × 10 kΩ (the 600-piece set on hand) |
| 220 µF + 100 nF | bulk + decoupling on 5 V |
| [DFRobot EC11 encoder](https://www.bastelgarage.ch/bauteile/schalter-taster/ec11-rotary-encoder-module) | with push button |
| [Gravity digital buzzer](https://www.bastelgarage.ch/bauteile/audio/gravity-digital-buzzer-fur-arduino) | |
| [Precision female header strip](https://www.bastelgarage.ch/bauteile/stiftleisten-pinheader/prazision-buchsenleiste-female-1x40-polig-rm-2-54-mm) ×3 | digit sockets + display-board connector |
| [Rainbow ribbon cable](https://www.bastelgarage.ch/kabel-litzen/sonder-kabel/flachkabel-idc-fc-regenbogen-40p-28awg) | peel off 12 conductors; key the connector by pulling one pin |

Pin order (EBC vs CBE) is not standardised across TO-92 transistors: check the
datasheet of the exact parts received.

## Firmware: `mux7seg`

A hardware timer (GPTimer, 1 MHz) fires the ISR every slot (1 ms by default).
Per slot: all display pins off in one `GPIO_OUT_W1TC` write → a few µs dark
gap → the digit's segment mask and its anode on via `GPIO_OUT_W1TS`. Brightness
is a second alarm inside the slot that switches the digit off early.

The rules that keep it working, each with the failure it prevents:

- **The ISR and everything it touches live in internal RAM** (`IRAM_ATTR`,
  `DRAM_ATTR`, plus two `sdkconfig` options the component sets). During a flash
  write the cache is off; any flash access from the ISR then panics. Flash
  writes happen on OTA updates and roughly once a minute after the knob moves
  (`restore_value`), so a violation shows up as a crash a minute after cooking
  starts. Watch for hidden flash access: `const` tables, `switch` jump tables,
  logging, virtual calls.
- **Order inside the ISR is clear → wait → light.** The PNP keeps conducting
  for a few µs after its drive is removed (storage time); new segments during
  that window ghost onto the previous digit. Ghosts visible: raise
  `blank_time`, or drop the PNP base pull-up from 10 kΩ to 4.7 kΩ.
- **Shared state is single-writer, single-reader, one aligned 32-bit store
  each.** The main loop writes the masks, the ISR only reads them. Never make
  them 64-bit, never `memcpy` a struct of them, never read-modify-write them
  from both sides.
- **The timer is installed from a task pinned to the last core,** so its
  interrupt lands there, away from Wi-Fi on core 0.
- **Heartbeat:** the ISR counts scans; `update()` blanks the display and raises
  a component error if the count stops moving, instead of leaving one digit
  stuck at 100%.

## Decisions

Newest last. Each one records what was traded away.

1. **Real 7-segment digits instead of an M5Stack Dial.** Readable across the
   kitchen; the Dial's round screen is not.
2. **Discrete multiplexing instead of a TM1637 module.** Chosen deliberately, to
   learn the layer underneath. Gains: 5 V anode headroom (even brightness
   despite Vf spread; the TM1637 at 3.3 V has ~1 V of headroom), smooth PWM
   dimming instead of 8 steps. Costs: ~150 solder joints instead of ~60, and a
   custom component to maintain across ESPHome updates. The TM1637 keeps
   scanning when the ESP crashes; this design doesn't, hence the heartbeat.
3. **ESP32-S3 instead of the C6.** 16 GPIOs needed (the C6 Zero is too small),
   and a second core for the scan ISR.
4. **Two boards.** Passive display board flush behind the front, driver board
   anywhere. Each testable on its own.
5. **Home Assistant owns the timer.** Survives reboots, shows on the phone,
   enables several timers later. Costs: needs HA for every start/pause/cancel.
6. **Offline: refuse, don't fork.** Without HA the device refuses to change the
   timer rather than running a local one that would need reconciling. A running
   timer still counts down and rings from its cached deadline.
7. **150 Ω segment resistors** instead of the computed 120 Ω: what the resistor
   set on hand has. ~15% less current, more margin if the scan ever hangs.

## Bring-up plan

1. Map one LTS-3401 digit in diode mode; confirm the pinout table.
2. Breadboard one segment: 5 V → 150 Ω → segment → NPN. Measure V_BE, V_CE(sat)
   and the real current. Swap the 1 kΩ base resistor for 47 kΩ to see the
   active region.
3. Add one digit switch. Try driving the PNP from the GPIO directly first, to
   see why the level shifter exists.
4. Two digits, multiplexed slowly (1 Hz → 1 kHz), then remove the blank to see
   ghosting, then put it back.
5. Full firmware on the breadboard; HA integration; stress test: 48 h of `88.88`,
   repeated OTA updates, knob spinning across an NVS flush, Wi-Fi pulled
   mid-timer, power cycle mid-timer.
6. Perfboard: display board first (passive, test each segment with 5 V through
   150 Ω), then the driver board.

## Open questions

- How timers should look on iOS beyond the notification: a Live Activity?
- Several timers (pasta, sauce, oven) with the knob cycling between them.
- Dedicated GPIO for the segment lines (S3 feature: 8 pins written in one CPU
  instruction). Pure experiment; not needed at 1 kHz.
