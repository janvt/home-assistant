# home-assistant

My Home Assistant setup: the bits that live in files rather than in the HA UI.

| Directory | What it is |
|-----------|------------|
| [`streamdeck/`](streamdeck/) | Two Stream Decks — a Plus on a Raspberry Pi (Docker) and a Plus XL on the Mac (native, with a local-action extension for controlling macOS). Has its own [README](streamdeck/README.md). |
| [`m5stack/`](m5stack/) | ESPHome configs for three M5Stack devices (Core, CoreS3, Dial) used as wall/desk controllers, plus [`core/m5-core-wifi-meter.yaml`](m5stack/core/m5-core-wifi-meter.yaml): an alternative firmware that turns the Core into a handheld Wi-Fi signal meter. |
| [`kitchen-timer/`](kitchen-timer/) | A DIY 7-segment kitchen timer: ESPHome config with a custom software-multiplexing display component. The timer itself is an HA `timer` helper; the device sets, starts and mirrors it. Has its own [README](kitchen-timer/README.md). |
| [`guest-eink/`](guest-eink/) | The guest room e-ink display: a 7.5" black/white/red Waveshare panel on an ESP32 showing the guest's name, the weather and a QR code for the guest Wi-Fi, in four languages. With [`packages/guest_wifi.yaml`](packages/guest_wifi.yaml), [`scripts/rotate_guest_wifi_password.yaml`](scripts/rotate_guest_wifi_password.yaml) and an automation, a guest name change rotates the UniFi guest Wi-Fi password and switches the network on or off. Has its own [README](guest-eink/README.md). |
| [`automations/`](automations/) | Home Assistant automations kept in version control. |
| [`blueprints/automation/janvt/road_closure_notice.yaml`](blueprints/automation/janvt/road_closure_notice.yaml) | The **Road closure notice** blueprint: one automation per person, made in the HA UI, for the closures of their roads (Axenstrasse, Gotthard tunnel, A2/A4 by direction) on their phone, on their days and hours, with an optional evening reminder. Saved in HA with `blueprint/save`; HA re-imports it from `source_url` once it's on `main`. |
| [`dashboards/weather/`](dashboards/weather/) | The Weather dashboard: MeteoSwiss (the forked integration) for Altdorf, Andermatt, Schlieren and four mountains, with warnings, SLF, Bergfex, IMIS and webcams. `locations.py` is the source of truth, `sync.py` pushes it. Has its own [README](dashboards/weather/README.md). |
| [`dashboards/trains/`](dashboards/trains/) | The Trains debug dashboard for Frigate's train detection on a full-resolution crop of the tracks: live and debug picture, detection state, tuning switches, Frigate's health and 24-hour history. `sync.py` pushes it and enables the diagnostics it needs. Has its own [README](dashboards/trains/README.md). |
| [`dashboards/infrastructure/`](dashboards/infrastructure/) | The Infrastructure dashboard: the Gotthard road tunnel's queues, closures, traffic messages and portal webcams, from the Gotthard integration, and the alpine passes nearby, from the Alpine Passes integration. `sync.py` pushes it. Has its own [README](dashboards/infrastructure/README.md). |
| [`dashboards/vpn/`](dashboards/vpn/) | The VPN dashboard: the WireGuard VPN's free AWS egress used this month, per peer, the AWS bill and 30 days of history. Not in the sidebar; the VPN alert pills open it. Has its own [README](dashboards/vpn/README.md). |
| [`dashboards/mobile-alerts/`](dashboards/mobile-alerts/) | The alert pills on the Mobile dashboard: a row of icons that never wraps, and an Alerts sub-page. `pills.py` is the source of truth, `sync.py` loads it into the integration below. Has its own [README](dashboards/mobile-alerts/README.md). |
| [`custom_components/alert_pills/`](custom_components/alert_pills/) | The **Alert Pills** integration that evaluates the pills, with options (switch pills or groups off, card only, row size) you can change from the phone. Installed through HACS from this repo ([`hacs.json`](hacs.json)). |
| [`ha-scene-tracker.yaml`](ha-scene-tracker.yaml) | The `input_select.active_scene` helper plus one automation per scene. Both Stream Decks read this to highlight the active scene. |

## Tests

None of it needs hardware to test. Everything is validated offline against
stubbed decks and a stubbed macOS bridge:

```bash
task -d streamdeck test
```

That creates `.venv-test/` on first run and executes the suite in
[`tests/`](tests/) — around 140 checks, a few seconds. To run it by hand:

```bash
python3 -m venv .venv-test && .venv-test/bin/pip install -r requirements-test.txt && .venv-test/bin/python -m pytest
```

| File | Covers |
|------|--------|
| [`test_deck_contract.py`](tests/test_deck_contract.py) | The three-way agreement between each deck's `spec.py`, its `configuration.yaml` and the images the renderer produces — including that **every position a dial can physically reach** resolves to a frame that exists. |
| [`test_deck_config.py`](tests/test_deck_config.py) | Both deck configs through the app's real pydantic models: key counts vs hardware, dial pairing, page navigation, `mac.*` services having handlers, and every template rendering. |
| [`test_icon_render.py`](tests/test_icon_render.py) | `generate_icons.py` — geometry scaling, the MDI codepoint map, and the rendered pixels (label placement, the gap INFO tiles leave for a live value, gauge fill growing with the value). |
| [`test_upstream_patch.py`](tests/test_upstream_patch.py) | The one place this repo edits installed upstream source, end to end against a copy: idempotency, upgrading an older patch, and refusing to write when upstream has moved. |
| [`test_esphome_configs.py`](tests/test_esphome_configs.py) | The ESPHome device YAML (`m5stack/`, `kitchen-timer/`, `guest-eink/`): duplicate keys, undefined substitutions, `id(...)` references that no `id:` declares, missing `includes:` headers, inline credentials. Plus ESPHome's own validator, opt-in. |
| [`test_kitchen_timer_helpers.py`](tests/test_kitchen_timer_helpers.py) | Compiles and runs the kitchen timer's C++ helpers on the host: parsing Home Assistant's `finishes_at` timestamp (timezone sign, fractional seconds) and `remaining` duration. |
| [`test_trains_dashboard.py`](tests/test_trains_dashboard.py) | The Trains dashboard: plain JSON, only Frigate entities, and every diagnostic the sync enables is on the page. |
| [`test_infrastructure_dashboard.py`](tests/test_infrastructure_dashboard.py) | The Infrastructure dashboard: plain JSON, exactly the Gotthard integration's and the passes' entities, the pass tables render, and its message templates parse and strip the "Freigegeben:". |
| [`test_road_closure_blueprint.py`](tests/test_road_closure_blueprint.py) | The road closure blueprint: every input used, and its templates run as HA runs them (strict) on the integration's attribute shapes: a restart sends nothing, a closure on several roads is sent once, only new closures, only on the days and hours chosen. |
| [`test_weather_dashboard.py`](tests/test_weather_dashboard.py) | The Weather dashboard: every details button, tapped tile and back arrow lands on a view that exists, every place has a page, the comparison graphs cover every location, and templates parse. |
| [`test_mobile_alerts.py`](tests/test_mobile_alerts.py) | The alert pills: the row never grows past one line for any number of active pills or row size, a rebuild touches only the row and the Alerts page (and is idempotent, and replaces the pre-integration row), templates compile, the definitions match what the integration accepts, and the integration installs through HACS. |
| [`test_kitchen_co2_status_led.py`](tests/test_kitchen_co2_status_led.py) | The kitchen CO2 status LED automation: renders its own colour-level template across the ppm range (including the 50 ppm falling deadband) and checks the `numeric_state` triggers sit exactly where that template changes level. |
| [`test_guest_wifi.py`](tests/test_guest_wifi.py) | The guest Wi-Fi rotation: the longest password the script can generate still fits the display's version 3 QR code, and the automation, script, package and display agree on the entity and rest_command names they share. |
| [`test_ha_yaml.py`](tests/test_ha_yaml.py) | Automations, and the scene-tracker seam: a scene a deck highlights must be an option `input_select.active_scene` can actually hold. |
| [`test_repo_hygiene.py`](tests/test_repo_hygiene.py) | No tokens, `.env` files or generated icons in git (asked of git itself, not of `.gitignore`), and the LaunchAgent/Taskfile pointing at files that exist. |
| [`test_ext_selftest.py`](tests/test_ext_selftest.py) | Runs `streamdeck/ext/`'s own 34-test unittest suite, so one command covers everything. |

Why these and not "unit tests for each function": nothing here has interesting
logic, and everything here has interesting *seams*. A wrong value in one of
these files does not crash — one key silently stops working, a dial goes blank
at the bottom of its range, an automation never fires. The suite is aimed at
that class of quiet failure, and each test says which one it is guarding.

### The alert_pills integration

[`tests_alert_pills/`](tests_alert_pills/) runs the integration inside Home
Assistant's own test harness: entity ids, the count and the row, dismissing
(and a dismissal surviving a reload), every option, and all of `pills.py`
loading. It needs a newer Python than the Pi's and pins its own pytest, so it
has its own venv:

```bash
task -d streamdeck test:alert-pills
```

### ESPHome validation

ESPHome's own validator is stronger than anything above but needs the `esphome`
package and network access (one config pulls an external component from GitHub,
and every `mdi:` image is fetched individually):

```bash
task -d streamdeck test:esphome
```

That target builds a **separate** `.venv-esphome/`, and has to: ESPHome requires
pydantic v2 while the Stream Deck app pins `pydantic<2`, so a shared venv
silently breaks whichever was installed first. CI keeps them in separate jobs
for the same reason.

Two configs are currently expected to fail it, recorded as `xfail` in
`tests/test_esphome_configs.py`: the Core and CoreS3 displays declare
`model: M5CORE2`, which on current ESPHome requires an explicit `psram:` block
that neither file has.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the suite on every
push and pull request against Python 3.11 and 3.13, then renders both decks'
image sets end to end. The ESPHome validation is a separate job. macOS-only
paths are a manual `workflow_dispatch` job, since the Mac-specific coverage is
one test and macOS runners bill at 10x.
