# Denise's dashboard

The **Denise** dashboard (`/dashboard-denise/home`) is the default for
Denise's login. She lives in Altdorf, not here, so it's about the town and the
road out of it, with no controls for any room. It isn't in the sidebar; she
gets it as her default (her **Profile → Appearance → Dashboard**, set while
logged in as her, not **Set as default** in Settings → Dashboards, which
changes it for everyone on Auto).

It's full screen: kiosk-mode (HACS) hides the header and the sidebar
(`KIOSK` in `build.py`). Open it with `?disable_km` on the URL to edit it in
the UI or get the sidebar back.

- **Alerts:** her own set of alert pills (`PILLS` in `build.py`): Altdorf's
  weather now and the forecast, föhn, frost and snow, pollen, the Axenstrasse
  and the Gotthard, the Schächen and the lake, holidays and records. A chip
  per pill while it's on; tapping one opens the **Alerts** sub-page with a
  card per active pill.
- **Weather in Altdorf:** MeteoSwiss warnings, the forecast, today's high,
  low, rain and sun, wind, gusts, rain now, humidity, hail while the radar
  sees any, and the hourly forecast. **More weather** opens Altdorf on the
  Weather dashboard.
- **Föhn:** the measured Föhn index, the outlook from the pressure across the
  Alps (Lugano − Kloten) and both over 48 hours, the same section as on the
  Weather dashboard.
- **Axenstrasse (A4):** open or closed, traffic counted, the next closure,
  vehicles and speed at Sisikon each way, the closures to come from its
  calendar, and vehicles per hour over 7 days.

| File | What |
|------|------|
| [`build.py`](build.py) | Builds the whole dashboard config from the Weather, Infrastructure and Mobile alerts builders. Pure functions. |
| [`sync.py`](sync.py) | Creates the dashboard if needed (not in the sidebar) and pushes it. |

## Her pills

They're the integration's own `binary_sensor.pill_<key>`, the ones on the
Mobile dashboard, picked by key; there's no second set of sensors. So:

- a pill switched off in the integration's options (Choose alerts) is gone
  from her dashboard too;
- dismissing is shared, so her cards have no hold action, and a pill Jan
  dismissed still shows for her;
- her row has one chip per pill, not the Mobile row's fixed slots. With a
  short list, few are on at once; past about ten the chips wrap.

To change her set, edit `PILLS` and sync. A key that isn't in `pills.py` fails
the tests.

```bash
.venv-test/bin/python dashboards/denise/sync.py            # dry run
.venv-test/bin/python dashboards/denise/sync.py --apply
```

It uses the same `dashboards/.env` as the other dashboards. **The script owns
this dashboard:** a card added in the HA UI is gone after the next `--apply`.
