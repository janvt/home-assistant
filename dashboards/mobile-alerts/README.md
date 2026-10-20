# Mobile dashboard alert pills

A row of small icons under the weather chips on the **Mobile** dashboard. Each
icon is a condition worth knowing about: smoke, the fridge left open, föhn in
Altdorf, a bluebird day tomorrow, waste collection. It only shows while that
condition is true. Tapping any icon opens the **Alerts** sub-page
(`/dashboard-mobile/weather-alerts`) with a full card per active alert and,
grouped by topic, every alert's rule and the live values it checks.

| File | What |
|------|------|
| [`pills.py`](pills.py) | The pills, in priority order: template, icon, colour, group, and what the Alerts page shows. **The source of truth.** |
| [`build.py`](build.py) | Turns `pills.py` into the row and the sub-page and splices them into the dashboard config. Pure functions. |
| [`sync.py`](sync.py) | Pushes it all to Home Assistant: creates or updates the helpers, then saves the dashboard. |

## How it works

- Each pill is a UI **template helper**, `binary_sensor.pill_<key>`. It's a
  config entry, so you can see it under Settings → Helpers, but its template
  belongs to `pills.py`: a change made in the UI is undone by the next sync.
- `sensor.weather_alerts_active` counts the `pill_` sensors that are on. It
  picks up new pills by itself.
- **The row never wraps.** Mushroom wraps chips onto a second line and card-mod
  isn't installed, so the row has a fixed number of places (`PLACES = 6`).
  Place *i* shows the *i*-th active pill in `pills.py` order. With more pills on
  than places, the last place shows "+N" instead. With none on, the row is hidden.
- The weather chips row above it is never touched. `build.apply` refuses to run
  if the first card on the dashboard isn't that row any more.

## Changing a pill

1. Edit `pills.py`. Order matters: the first entries take the places in the
   row when many are active.
2. Run the tests: `task -d streamdeck test` (or `pytest tests/test_mobile_alerts.py`).
3. Copy `dashboards/.env.example` to `dashboards/.env`, fill in the token, then:

```bash
.venv-test/bin/python dashboards/mobile-alerts/sync.py
```

That's a dry run: it lists which helpers it would create or update, and whether
the dashboard would change. Add `--apply` to do it. The dashboard config HA had
before is saved to `backups/` first, so a bad push can be undone by pasting it
into the raw configuration editor.

`sync.py` needs the `websockets` package, which the test venv already has
(the Stream Deck app depends on it).

## Data sources

The pills read entities from all over the house: MeteoSwiss (the forked
integration, including its forecast summary and warning sensors), SLF bulletins and IMIS
stations, Bergfex, Aqara/Zigbee door and temperature sensors, the Nuki lock,
Athom plugs, the ultimatesensor, Blitzortung, FlightRadar24, Swiss public
transport, Workday (Uri and Zürich), calendars (birthdays, Swiss holidays,
copebit, copebit vacations, iCloud Home, ZAKU waste collection), Meross
thermostats, Backup, UniFi, Electricity Maps, Sonos, Spotify and `update.*`.
"Home" is Altdorf (HA's home zone): the rain, frost, shades and fog pills read
Altdorf's sensors. Schlieren and Zürich only appear as a comparison (föhn). A renamed entity doesn't
break anything loudly: its pill just stops turning on. The Alerts page shows
each pill's inputs, which is the quickest place to spot an `unavailable`.
