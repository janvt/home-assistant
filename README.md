# home-assistant

My Home Assistant setup: the bits that live in files rather than in the HA UI.

| Directory | What it is |
|-----------|------------|
| [`streamdeck/`](streamdeck/) | Two Stream Decks — a Plus on a Raspberry Pi (Docker) and a Plus XL on the Mac (native, with a local-action extension for controlling macOS). Has its own [README](streamdeck/README.md). |
| [`m5stack/`](m5stack/) | ESPHome configs for three M5Stack devices (Core, CoreS3, Dial) used as wall/desk controllers. |
| [`automations/`](automations/) | Home Assistant automations kept in version control. |
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
| [`test_esphome_configs.py`](tests/test_esphome_configs.py) | The `m5stack/` YAML: duplicate keys, undefined substitutions, `id(...)` references that no `id:` declares, missing `includes:` headers, inline credentials. Plus ESPHome's own validator, opt-in. |
| [`test_ha_yaml.py`](tests/test_ha_yaml.py) | Automations, and the scene-tracker seam: a scene a deck highlights must be an option `input_select.active_scene` can actually hold. |
| [`test_repo_hygiene.py`](tests/test_repo_hygiene.py) | No tokens, `.env` files or generated icons in git (asked of git itself, not of `.gitignore`), and the LaunchAgent/Taskfile pointing at files that exist. |
| [`test_ext_selftest.py`](tests/test_ext_selftest.py) | Runs `streamdeck/ext/`'s own 34-test unittest suite, so one command covers everything. |

Why these and not "unit tests for each function": nothing here has interesting
logic, and everything here has interesting *seams*. A wrong value in one of
these files does not crash — one key silently stops working, a dial goes blank
at the bottom of its range, an automation never fires. The suite is aimed at
that class of quiet failure, and each test says which one it is guarding.

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
push and pull request against Python 3.10 and 3.13, then renders both decks'
image sets end to end. The ESPHome validation is a separate job. macOS-only
paths are a manual `workflow_dispatch` job, since the Mac-specific coverage is
one test and macOS runners bill at 10x.
