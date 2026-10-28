# Infrastructure dashboard

The **Infrastructure** dashboard (`/dashboard-infrastructure/gotthard`) is for
the roads and tunnels around us. For now it has one view, the Gotthard road
tunnel:

- **Right now:** whether the tunnel is open, the next announced closure, and
  for each portal the queue (km) and the time it costs (min). The north
  portal's queue is southbound before Göschenen, the south portal's northbound
  before Airolo.
- **Webcams** at both portals, on the A2.
- **Traffic messages** about the tunnel and the pass road, and the tunnel
  closures announced, with their times.
- **History:** queues and delays over 24 hours, the tunnel over 7 days, and the
  longest delay per day over 30 days.

The **Roads** view (`/dashboard-infrastructure/roads`) opens with the closures
to come, from the integration's calendars (a week as a list; restrictions
too if they're turned on in its options). Then it has the Axenstrasse
(open or closed, what closes it, and the closures announced) and the closures
of the A2 and the A4 each way: how many now, and the next five announced. Its
entities are the integration's **National roads** device.

The **Traffic** view (`/dashboard-infrastructure/traffic`) needs the
integration's traffic counters, which are opt in (its options, with their own
API key). It has a queue forming before each Gotthard portal and the travel
times Altdorf ↔ Göschenen and Altdorf ↔ Stans; the speeds before the portals
over 24 hours; two maps with every station's speed, southbound and
northbound; a table of every station now (vehicles, speed, lorries, each
way); and, per hour over 7 days, the traffic at Göschenen and on the
Axenstrasse, the lorries at Göschenen and the travel times.

The **Passes** view (`/dashboard-infrastructure/passes`) has the alpine passes
within about 40 km of home: Klausen, Ibergeregg, Susten, Pragel, Oberalp,
Gotthard, Lukmanier and Furka.

- **Passes nearby:** a Mushroom card per pass, its icon and color by status:
  green open, amber open with restrictions, orange partly open, red closed,
  light blue closed for the winter, grey unknown. The second line has the
  status, temperature and since when; a badge shows snow chains or truck
  limits. Needs Mushroom (HACS).
- **Conditions:** the site's own words for the status, with snow chains and
  truck limits, when it last changed, and the temperature and weather.
- **Notices:** night closures, weight limits and the like, pass by pass.
- **History:** which passes were open over 7 days, and their temperatures over
  48 hours.

The Gotthard, Roads and Traffic views come from the Gotthard integration
([janvt/homeassistant-gotthard](https://github.com/janvt/homeassistant-gotthard),
installed through HACS), which reads FEDRO's traffic messages from
opentransportdata.swiss. The Passes view comes from the Alpine Passes
integration
([janvt/homeassistant-alpine-passes](https://github.com/janvt/homeassistant-alpine-passes),
private for now, copied over SSH), which reads alpen-paesse.ch of IG
Alpenpässe. Its entry must have the same passes as `PASSES` in `build.py`: the
sync refuses to save a dashboard naming an entity HA doesn't have.

| File | What |
|------|------|
| [`build.py`](build.py) | Builds the whole dashboard config. Pure functions. `ENTITIES` is every entity the Gotthard integration makes, `PASS_ENTITIES` every one of the passes. |
| [`sync.py`](sync.py) | Creates the dashboard if needed (in the sidebar) and pushes it. Refuses to drop a view HA has that `build.py` doesn't make (`--drop-views` overrides). |

```bash
.venv-test/bin/python dashboards/infrastructure/sync.py            # dry run
.venv-test/bin/python dashboards/infrastructure/sync.py --apply
```

It uses the same `dashboards/.env` as the other dashboards. **The script owns
this dashboard:** a card added in the HA UI is gone after the next `--apply`.
A whole view HA has that `build.py` doesn't make stops the sync instead, so a
view made in the UI, or synced from another branch, isn't lost.
