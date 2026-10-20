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
  the current weather, the daily forecast, wind, rain, humidity, a MeteoSwiss
  warning tile when one is out, and for Andermatt the Gemsstock webcam, the
  avalanche level and the snow depths. Then 48-hour comparison graphs, and a
  section per mountain or pass with its freezing level.
- **One page per location:** MeteoSwiss warnings in full, hourly and daily
  forecast, wind gauges, sun and rain, 72-hour trends. Altdorf adds Blitzortung
  lightning. Andermatt adds the
  webcams, the SLF bulletin, both Bergfex ski areas, the Bergfex snow maps with
  their colour legend, and the IMIS stations Gütsch, Culmatsch and Gross Schijen.
- **One page per mountain:** the forecast for the summit's altitude, freezing
  level, and for Gross Windgällen the measured values of its IMIS station.

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
