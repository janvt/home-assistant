# Alert Pills

The integration behind the alert pills on the Mobile dashboard. It evaluates
the pills defined in [`dashboards/mobile-alerts/pills.py`](../../dashboards/mobile-alerts/pills.py),
which `sync.py` there loads with `alert_pills.load`; its options switch pills
or whole groups off, keep pills out of the row, and set the row size.

How it all fits together, installing it through HACS, and the services:
[`dashboards/mobile-alerts/README.md`](../../dashboards/mobile-alerts/README.md).

| File | What |
|------|------|
| `manager.py` | Renders the pills' templates, remembers when each turned on and was dismissed (stored, so restarts keep dismissals), works out the row. |
| `logic.py` | Which pills show and which get a place in the row. No HA imports: the repo's plain suite tests it. |
| `const.py` | Entity ids, option names and limits, shared with `build.py`. No HA imports either. |
| `config_flow.py` | Setup (no questions) and the options form. |
| `binary_sensor.py`, `sensor.py` | `binary_sensor.pill_<key>`, `sensor.weather_alerts_active` and `sensor.alert_pills_row`. |
