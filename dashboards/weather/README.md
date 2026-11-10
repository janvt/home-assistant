# Weather dashboard

The **Weather** dashboard (`/dashboard-weather`), built from the forked
[MeteoSwiss integration](https://github.com/janvt/homeassistant-meteoswiss)
plus SLF, Bergfex, the Andermatt webcams and the SED's earthquakes.

| File | What |
|------|------|
| [`locations.py`](locations.py) | The places and what each has: weather and rain stations, webcams, ski areas, the SLF bulletin, IMIS stations. **The source of truth.** |
| [`build.py`](build.py) | Builds the whole dashboard config from `locations.py`. Pure functions. |
| [`sync.py`](sync.py) | Pushes it to Home Assistant. |

## What's on it

- **Overview:** one section per location (Altdorf, Andermatt, Schlieren) with
  the current weather, the daily forecast, today's high, low, rain and sun as
  badges, wind, rain now and in the last hour (radar), humidity, snow on the ground while there is any, a
  hail tile while the radar sees any, a MeteoSwiss warning tile when one is out, and for Andermatt the Gemsstock webcam, the
  avalanche level and the snow depths. Then 48-hour comparison graphs, and a
  section per mountain or pass with its freezing level and radar precipitation, and the FOEN river
  stations with a rising/falling trend against their 24-hour mean. Last, what
  MeteoSwiss downloaded (24 h and this month) and each place's Downloads
  switch, which pauses it. An earthquakes section shows the latest and the
  strongest quake and opens the Earthquakes page.
- **One page per location:** MeteoSwiss warnings in full, the ground
  temperature (5 cm) and snow depth, today's forecast and the lowest freezing
  level in 48 h, hourly and daily forecast, wind gauges, sun, the animated rain radar loop,
  radar rain (now and last hour) and hail next to the rain station's
  10-minute totals, 72-hour trends, and today and this month
  against the 1991–2020 normals with the records for the date. Altdorf adds
  Blitzortung lightning and the Föhn index and outlook; Altdorf and Andermatt
  show their freezing level. Altdorf and Andermatt show Luzern's pollen, Schlieren Zürich's.
  Andermatt adds the
  webcams, the SLF bulletin, both Bergfex ski areas, the Bergfex snow maps with
  their colour legend, and the IMIS stations Gütsch, Culmatsch and Gross Schijen.
- **Earthquakes** (`/dashboard-weather/earthquakes`, from the Overview's
  Earthquake details button): a map of every quake the Swiss Seismological
  Service (SED) located within 150 km in the last 30 days, the latest and the
  strongest, how many over 30 days, a table of those of magnitude 2 and up and
  one of the latest 25, and what a magnitude means (the integration's own
  scale). From the Swiss Earthquakes (SED) integration
  ([prusuino/ha_swiss_earthquakes](https://github.com/prusuino/ha_swiss_earthquakes),
  HACS). Its sensors end in the entry's radius and id (`_150km_cmbz`): if the
  entry is re-added, change `EARTHQUAKES` in `locations.py` and `QUAKE` in
  `dashboards/mobile-alerts/pills.py` together (a test checks they agree).
- **One page per mountain:** the forecast for the summit's altitude, today's
  forecast, freezing level now and lowest in 48 h, the radar loop over the
  summit, and for Gross Windgällen the measured values of its IMIS station.

## Notifications

`automations/meteoswiss_weather_notifications.yaml` sends a notification to
the phone when MeteoSwiss announces an orange or red warning for Altdorf
within 24 hours, when the radar sees a 50 % chance of hail over home, and
when strong south föhn is coming. It uses the integration's own triggers
(*Weather warning reached*, *Hail expected*, *Föhn expected*), which came
with v2.3.0-beta.1 and need Home Assistant 2026.11. Each one fires once when
its sensor reaches the level, not on every update. Without that version HA
refuses the automation (Settings → Repairs). The alert pills show the same
things for longer; the tests keep both on the same sensors and the same hail
threshold.

## Changing it

Edit `locations.py` (or `build.py` for layout), run the tests, then:

```bash
.venv-test/bin/python dashboards/weather/sync.py            # dry run
.venv-test/bin/python dashboards/weather/sync.py --apply
```

It uses the same `dashboards/.env` as the alert pills. **The script owns this
dashboard:** a card added in the HA UI is gone after the next `--apply`. The
config HA had before goes to `backups/` (git-ignored), so it can be restored
from the raw configuration editor.
