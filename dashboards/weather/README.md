# Weather dashboard

The **Weather** dashboard (`/dashboard-weather`), built from the forked
[MeteoSwiss integration](https://github.com/janvt/homeassistant-meteoswiss)
plus SLF, Bergfex and the Andermatt webcams.

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
  switch, which pauses it.
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
- **One page per mountain:** the forecast for the summit's altitude, today's
  forecast, freezing level now and lowest in 48 h, the radar loop over the
  summit, and for Gross Windgällen the measured values of its IMIS station.

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
