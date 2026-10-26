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
| [`build.py`](build.py) | Turns `pills.py` into the definitions the integration loads, the row and the sub-page, and splices them into the dashboard config. Pure functions. |
| [`sync.py`](sync.py) | Pushes it all to Home Assistant: loads the pills into the integration, creates the few helpers they read, then saves the dashboard. |
| [`custom_components/alert_pills/`](../../custom_components/alert_pills/) | The **Alert Pills** integration that evaluates the pills, installed through HACS from this repo. |

## How it works

- The **Alert Pills** integration evaluates every pill's template itself. Each
  pill is `binary_sensor.pill_<key>`, all under one device, with no helper per
  pill. `sync.py` sends the definitions with `alert_pills.load`, so changing a
  pill needs no HA restart; only a change to the integration's own code does.
- **Options, from the phone:** Settings → Devices & services → Alert Pills →
  Configure, or **Choose alerts** at the top of the Alerts page:
  - *Switched off*: never evaluated, never in the row or the count. Its sensor
    is unavailable.
  - *Groups switched off*: the same for every pill in a group.
  - *Card only*: counted and on the Alerts page, but no place in the row.
  - *Icons in the row*: 1 to 10, 6 by default.
- `sensor.weather_alerts_active` counts the pills shown: on, switched on and
  not dismissed. `sensor.alert_pills_row` says how many of the row's places
  are in use, and its `slots` attribute holds each place's icon, colour and
  content. The integration renders the colours (`color_from` included) and
  `content`, and each pill has them as `color` and `content` attributes.
- **The row never wraps.** Mushroom wraps chips onto a second line and card-mod
  isn't installed, so the dashboard has 10 chips and each shows one slot or
  hides. Slots go to the active pills in `pills.py` order. With more pills on
  than places, the last place shows "+N" instead. With none on, the row is
  hidden.
- **Dismissing:** hold a card on the Alerts page to dismiss it; hold again to
  bring it back (`alert_pills.toggle_dismiss`). A dismissed pill leaves the row
  and the count until it turns off and on again, then it's back by itself. The
  safety pills in `CRITICAL` (smoke/CO, door, lock, fridge, heating while away)
  can't be dismissed. Dismissals survive an HA restart: the integration keeps
  when each pill turned on.
- Some pills compare against a limit you set: an `input_number` listed in
  `NUMBERS` in `pills.py` (the Reuss dog walk limit). `sync.py` creates it
  when it's missing and never touches its value; change it on the Alerts page.
- A few pills read a **Statistics** helper (`STATISTICS` in `pills.py`), e.g.
  Altdorf's 24-hour rain total for "muddy paths". `sync.py` creates those too.
- "Trains today" reads a **History stats** helper (`HISTORY_STATS`):
  `sensor.trains_today` counts how often `binary_sensor.train_passing` turned
  on since midnight. That one is a plain template helper (`TEMPLATES`) on
  Frigate's train-on-the-track sensor, held on for 30 s so a train that
  flickers out of the zone counts once. `sensor.trains_this_hour` counts the
  same per hour; both keep long-term statistics for the Trains dashboard's
  bar charts. The `_tele` versions (`binary_sensor.train_passing_tele`,
  `sensor.trains_today_tele`, `sensor.trains_this_hour_tele`) count the same
  from the iPhone camera `train_tele`, in parallel, to compare the two; the
  pill shows both counts while the cameras are compared, "Reolink|iPhone", and
  its Alerts card both last trains matched to the timetable.
- A pill with `content` shows that template next to its icon in the row, e.g.
  the number of trains.
- The weather chips row above it is never touched. `build.apply` refuses to run
  if the first card on the dashboard isn't that row any more.

## Installing the integration

Once, in HACS: ⋮ → Custom repositories → `https://github.com/janvt/home-assistant`,
type **Integration**. Download **Alert Pills** and restart Home Assistant.
`sync.py --apply` adds the integration itself. HACS installs from `main`, so a
change to `custom_components/alert_pills/` reaches HA after its PR is merged:
HACS then shows an update; install it and restart.

Before the integration, every pill was a UI template helper, with an
`input_datetime.pill_<key>_dismissed` each and `script.pill_toggle_dismiss`.
The first `sync.py --apply` removes those, so the integration's sensors take
over the same entity ids and keep their history. Pills dismissed at that
moment come back once.

## Changing a pill

1. Edit `pills.py`. Order matters: the first entries take the places in the
   row when many are active.
2. Run the tests: `task -d streamdeck test` (or `pytest tests/test_mobile_alerts.py`).
   A change to the integration also needs `task -d streamdeck test:alert-pills`.
3. Copy `dashboards/.env.example` to `dashboards/.env`, fill in the token, then:

```bash
.venv-test/bin/python dashboards/mobile-alerts/sync.py
```

That's a dry run: it lists which pills it would add, change or remove, which
helpers it would create or update, and whether the dashboard would change. Add
`--apply` to do it. The integration refuses the whole load if a template
doesn't compile. The dashboard config HA had before is saved to `backups/`
first, so a bad push can be undone by pasting it into the raw configuration
editor.

`sync.py` needs the `websockets` package, which the test venv already has
(the Stream Deck app depends on it).

## Data sources

The pills read entities from all over the house: MeteoSwiss (the forked
integration, including its forecast summary, warning and radar rain and hail sensors), SLF bulletins and IMIS
stations, Bergfex, Aqara/Zigbee door and temperature sensors, the Nuki lock,
Athom plugs, the ultimatesensor, Blitzortung, FOEN river data, MeteoSwiss pollen, Proxmox (node, guests, storages), FlightRadar24, Swiss public
transport, Workday (Uri and Zürich), calendars (birthdays, Swiss holidays,
copebit, copebit vacations, iCloud Home, ZAKU waste collection: cardboard only), Meross
thermostats, Backup, UniFi, Sonos, Spotify and `update.*`.
"Home" is Altdorf (HA's home zone): the rain, frost, shades and fog pills read
Altdorf's sensors. Schlieren and Zürich only appear as a comparison (föhn). A renamed entity doesn't
break anything loudly: its pill just stops turning on. The Alerts page shows
each pill's inputs, which is the quickest place to spot an `unavailable`.
