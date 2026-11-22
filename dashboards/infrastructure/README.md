# Infrastructure dashboard

The **Infrastructure** dashboard (`/dashboard-infrastructure/gotthard`) is for
the roads, tunnels, passes, flights and ski lifts around us. The Gotthard
view has the road tunnel:

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
(open or closed, traffic counted, and the next closure) and how many closures
the A2 and the A4 have each way now. What they are is in the calendar only:
lists of them here repeated it. Its
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
  a green check for open, an amber snowflake for open with restrictions (mostly
  snow on the road), an orange half circle for partly open, a red slashed
  circle for closed (for the winter too), grey for unknown. The second line
  has the status, temperature and since when; a badge shows snow chains or
  truck limits. Needs Mushroom (HACS).
- **Conditions:** when the integration last read alpen-paesse.ch (old if the
  site cannot be read), then the site's own words for the status, with snow
  chains and truck limits, when it last changed, and the temperature and
  weather.
- **Notices:** night closures, weight limits and the like, pass by pass.
- **History:** which passes were open over 7 days, and their temperatures over
  48 hours.

The **Flights** view (`/dashboard-infrastructure/flights`) has the planes
overhead, from the FlightRadar24 integration
([AlexandrErohin/home-assistant-flightradar24](https://github.com/AlexandrErohin/home-assistant-flightradar24),
HACS). Its area is the circle round home set in the integration's options.

- **Overhead now:** how many flights are in the area, just entered and just
  left, and the integration's own map card (`custom:flightradar24-card`,
  registered by the integration) with their tracks and a list under it.
- **Flight:** a card per flight overhead with its photo, route and progress
  (`custom:flightradar-flight-card`, HACS); with none overhead, the tracked
  ones. Metres, km and km/h, not FlightRadar24's feet and knots.
- **Tracked flights:** flights followed anywhere, by flight number, callsign
  or registration, with the fields to add and remove them. A tracked flight
  sends a notification to the phone when it leaves the gate, takes off, lands
  and reaches the gate, and when its delay crosses 15, 30, 60 or 120 min (or
  it's back on time): `automations/tracked_flight_changes.yaml`.
- **Most watched worldwide:** FlightRadar24's top ten, while the Most tracked
  switch is on.
- **Airport:** type an IATA or ICAO code (ZRH) for its arrivals and
  departures boards and today's punctuality. Until one is typed the airport
  sensors are unavailable, so their cards stay hidden behind a hint.
- **History:** flights overhead over 24 hours, the switch that stops every
  call to FlightRadar24, and the integration's update.

The **Andermatt** view (`/dashboard-infrastructure/andermatt`) has the lifts,
slopes, snow and car parks of Andermatt+Sedrun+Disentis, from the Andermatt
Live integration (`andermatt-live/` in this repository, copied over SSH), which
reads the resort's beta Live Dashboard every 10 minutes.

- **Overview:** a row per sector (Gemsstock, Andermatt-Oberalppass,
  Oberalppass-Dieni, Sedrun, Disentis): open or not, lifts and slopes open of
  all, km of slopes open, snow depth and new snow.
- **A section per sector:** its Open badge, the counts, snow and its car parks
  (free or full), then a table of its lifts (🟢 open, ⚪ closed, ❔ unknown,
  with type and first and last ride) and one of its slopes (status, colour,
  length). The tables are built from each sector's device in HA, so a lift or
  slope the site adds shows up without a change here.
- **History:** lifts open and km of slopes open per sector over 7 days, snow
  depth over 30 days.

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
| [`build.py`](build.py) | Builds the whole dashboard config. Pure functions. `ENTITIES` is every entity the Gotthard integration makes, `PASS_ENTITIES` every one of the passes, `FLIGHT_ENTITIES` every one of FlightRadar24's, `SKI_ENTITIES` every Andermatt Live sector's own (its lifts and slopes are in the tables). |
| [`sync.py`](sync.py) | Creates the dashboard if needed (in the sidebar) and pushes it. Refuses to drop a view HA has that `build.py` doesn't make (`--drop-views` overrides). |

```bash
.venv-test/bin/python dashboards/infrastructure/sync.py            # dry run
.venv-test/bin/python dashboards/infrastructure/sync.py --apply
```

It uses the same `dashboards/.env` as the other dashboards. **The script owns
this dashboard:** a card added in the HA UI is gone after the next `--apply`.
A whole view HA has that `build.py` doesn't make stops the sync instead, so a
view made in the UI, or synced from another branch, isn't lost.
