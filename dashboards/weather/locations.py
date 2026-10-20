"""What the Weather dashboard shows: the places, and the extras each one has.

Each entry here is one MeteoSwiss config entry. Valley locations have a
weather station (`station`: the prefix of its sensors) and a rain station;
mountains have only a forecast. Order is the order on the Overview.

The IMIS stations list their sensors explicitly: the SLF integration only
creates the ones a station measures, and wind-only stations have no snow.
"""

LOCATIONS = [
    dict(title="Altdorf", path="altdorf", icon="mdi:town-hall", weather="weather.altdorf_ur",
         station="altdorf", rain="sensor.bristen_10_minute_rain", stations_text="Altdorf · rain Bristen",
         slf="altdorf_9r5z"),
    dict(title="Andermatt", path="andermatt", icon="mdi:summit", weather="weather.andermatt",
         station="andermatt", rain="sensor.goscheneralp_10_minute_rain",
         stations_text="Andermatt · rain Göscheneralp",
         cams=["camera.andermatt_gemsstock", "camera.andermatt_baezberg"],
         # Bergfex resort id, name on the dashboard.
         ski=[("andermatt_gemsstock", "Gemsstock"), ("andermatt_oberalp_sedrun", "Oberalp – Sedrun")],
         slf="andermatt_9pb7", imis=["gos3_zwja", "tuj2_mr82", "urs1_prsf"]),
    dict(title="Schlieren", path="schlieren", icon="mdi:home-city", weather="weather.schlieren",
         station="zurich_fluntern", rain="sensor.uster_10_minute_rain",
         stations_text="Zürich / Fluntern · rain Uster"),
]

MOUNTAINS = [
    dict(title="Uri Rotstock", slug="uri_rotstock", icon="mdi:summit", elevation=2929),
    dict(title="Gross Windgällen", slug="gross_windgallen", icon="mdi:summit", elevation=3187, imis="sca1_spjp"),
    dict(title="Bristen", slug="bristen", icon="mdi:summit", elevation=3073),
    dict(title="Oberalppass", slug="oberalppass", icon="mdi:road-variant", elevation=2044),
]

SNOW = ["snow_height", "new_snow_1d", "air_temperature", "snow_surface_temperature",
        "humidity", "wind_speed", "wind_gust", "wind_direction"]
WIND = ["air_temperature", "humidity", "wind_speed", "wind_gust", "wind_direction"]
IMIS = {
    "gos3_zwja": dict(name="Gütsch", elevation=2209, sensors=SNOW),
    "tuj2_mr82": dict(name="Culmatsch", elevation=2262, sensors=SNOW),
    "urs1_prsf": dict(name="Gross Schijen", elevation=2784, sensors=WIND),
    "sca1_spjp": dict(name="Gross Windgällen", elevation=3187, sensors=WIND),
}
