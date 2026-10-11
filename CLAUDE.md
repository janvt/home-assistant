# CLAUDE.md

Jan's Home Assistant setup: everything that lives in files rather than in the
HA UI. Start with [README.md](README.md) for the layout; each subproject has its
own README with the full context.

| Path | What | Read first |
|------|------|------------|
| `streamdeck/` | Two Stream Decks (Pi + Docker, Mac native with a local-action extension) | `streamdeck/README.md` |
| `m5stack/` | ESPHome configs for M5Stack Core, CoreS3, Dial | the YAML headers |
| `kitchen-timer/` | DIY 7-segment kitchen timer: ESPHome config, custom `mux7seg` component, HA-owned timer | `kitchen-timer/README.md` (architecture, hardware, decision log) |
| `automations/` | HA automations kept in version control | |
| `ha-scene-tracker.yaml` | `input_select.active_scene` + one automation per scene | |

## Testing

```bash
task -d streamdeck test            # whole suite (creates .venv-test/)
task -d streamdeck test:esphome    # ESPHome's own validator, separate venv
```

Nothing needs hardware. The suite targets **seams, not functions**: a wrong
value in these files doesn't crash, one thing quietly stops working. Each test
names the failure it guards against; keep new tests in that style.

- ESPHome needs pydantic v2, the Stream Deck app pins `<2`: they never share a venv.
- Known gaps against current ESPHome are recorded as non-strict `xfail` with a
  reason (`KNOWN_VALIDATION_GAPS`), not skipped.
- Python floor is 3.11 (the Pi), ceiling 3.13 (the Mac). CI runs both.

## Conventions

- **Secrets:** never inline. ESPHome uses `!secret`, and every secret name must
  be in `KNOWN_SECRETS` in `tests/test_esphome_configs.py`. A new device
  directory needs a `.gitignore` rule for its `secrets.yaml` and a path in
  `test_git_actually_ignores_the_sensitive_paths`. HA tokens live in `.env`,
  only `.env.example` is tracked.
- **New ESPHome device:** add its directory to `esphome_configs()` in
  `tests/conftest.py`. Declare ids as `id: name` on their own line (comments
  above, not trailing), or `test_every_referenced_id_is_declared` can't see them.
- **Automations:** `alias`, `triggers`, `actions`, and a unique `id`.
- **Changes go through a branch and PR** (`claude/<topic>`), not straight to `main`.

## Kitchen timer specifics

The `mux7seg` ISR has rules that compile fine and fail later. Read the
"Firmware" section of `kitchen-timer/README.md` before touching
`components/mux7seg/mux7seg.cpp`: nothing the ISR touches may live in flash,
the clear → wait → light order inside the ISR is load-bearing, and the shared
masks must stay single 32-bit stores.
