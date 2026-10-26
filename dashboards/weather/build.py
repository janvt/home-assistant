"""The Weather dashboard (`dashboard-weather`), built from `locations.py`.

`build()` returns the whole dashboard config. Unlike the Mobile dashboard,
this one is owned by the script end to end: a card added in the UI is gone
after the next sync.

Views: an Overview (one section per location and mountain, plus comparison
graphs), then one sub-page per location and mountain.
"""
from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

_loc = runpy.run_path(str(Path(__file__).resolve().parent / "locations.py"))
LOCATIONS: list[dict[str, Any]] = _loc["LOCATIONS"]
MOUNTAINS: list[dict[str, Any]] = _loc["MOUNTAINS"]
IMIS: dict[str, dict[str, Any]] = _loc["IMIS"]
RIVERS: list[dict[str, Any]] = _loc["RIVERS"]
POLLEN_TYPES: list[str] = _loc["POLLEN_TYPES"]

DASHBOARD = "dashboard-weather"
BASE = f"/{DASHBOARD}"
WARN_LEVELS = ["yellow", "orange", "red"]
# Bergfex's legend for its fresh-snow maps. The colours cycle, so the same
# hue means two different amounts: the note under the legend says so.
SNOW_SCALE = [("#DBFE4B", 1), ("#43E749", 5), ("#FFB805", 10), ("#5CFDC6", 15), ("#00BEFF", 20), ("#005DFF", 30),
              ("#FF68FE", 40), ("#FFFF39", 50), ("#FF7806", 70), ("#FF1B82", 90), ("#791280", 120)]
IMIS_NAMES = {"snow_height": "Snow depth", "new_snow_1d": "New snow 24 h", "air_temperature": "Air temp",
              "snow_surface_temperature": "Snow surface", "humidity": "Humidity", "wind_speed": "Wind",
              "wind_gust": "Gusts", "wind_direction": "Direction"}


# ── card helpers ────────────────────────────────────────────────────────────
def nav(path: str) -> dict[str, Any]:
    return {"action": "navigate", "navigation_path": f"{BASE}/{path}"}


def tile(entity: str, name: str | None = None, **extra: Any) -> dict[str, Any]:
    card = {"type": "tile", "entity": entity, "vertical": True}
    if name:
        card["name"] = name
    card.update(extra)
    return card


def gauge(entity: str, name: str, maximum: int, steps: list[int]) -> dict[str, Any]:
    colours = ["#43a047", "#fdd835", "#fb8c00", "#e53935"]
    return {"type": "gauge", "entity": entity, "name": name, "min": 0, "max": maximum, "needle": True,
            "segments": [{"from": f, "color": c} for f, c in zip(steps, colours)]}


def hist(entities: list[str], title: str, hours: int = 48) -> dict[str, Any]:
    return {"type": "history-graph", "title": title, "hours_to_show": hours,
            "entities": [{"entity": e} for e in entities]}


def cam(entity: str, **extra: Any) -> dict[str, Any]:
    card = {"type": "picture-entity", "entity": entity, "camera_view": "auto", "show_state": False, "show_name": True}
    card.update(extra)
    return card


def sensor(loc: dict[str, Any], key: str) -> str:
    return f"sensor.{loc['station']}_{key}"


def slug(loc: dict[str, Any]) -> str:
    """The MeteoSwiss entry's slug: its forecast sensors are sensor.<slug>_*."""
    return loc["weather"].split(".")[1]


def radar(place_slug: str, kind: str) -> str:
    """MeteoSwiss's weather radar for an entry: rain_rate, rain_last_hour, hail_probability or hail_size."""
    return f"sensor.{place_slug}_radar_{kind}"


def radar_loop(place_slug: str) -> dict[str, Any]:
    """The animated rain radar, the last 20 minutes over 60 km around the place."""
    return cam(f"image.{place_slug}_radar_loop", name="Rain radar, last 20 min", tap_action={"action": "more-info"},
               grid_options={"columns": 12})


def hail_tile(place_slug: str, **extra: Any) -> dict[str, Any]:
    """Hail probability, shown only while the radar sees any."""
    e = radar(place_slug, "hail_probability")
    return tile(e, "Hail", visibility=[{"condition": "numeric_state", "entity": e, "above": 0}], **extra)


def radar_cards(place_slug: str) -> list[dict[str, Any]]:
    return [tile(radar(place_slug, "rain_rate"), "Rain now (radar)"),
            tile(radar(place_slug, "rain_last_hour"), "Rain last hour (radar)"),
            tile(radar(place_slug, "hail_probability"), "Hail chance (radar)"),
            tile(radar(place_slug, "hail_size"), "Hail size (radar)")]


def details_button(title: str, tap: dict[str, Any]) -> dict[str, Any]:
    return {"type": "button", "name": f"{title} details", "icon": "mdi:chevron-right-circle-outline",
            "show_state": False, "tap_action": tap, "grid_options": {"columns": 12, "rows": 1}}


# ── MeteoSwiss warnings ─────────────────────────────────────────────────────
def _warn_visible(s: str) -> list[dict[str, Any]]:
    return [{"condition": "state", "entity": f"sensor.{s}_weather_warning_next_24_hours", "state": WARN_LEVELS}]


def warn_tile(s: str, tap: dict[str, Any] | None = None) -> dict[str, Any]:
    card = {"type": "tile", "entity": f"sensor.{s}_weather_warning_next_24_hours", "name": "Warning (24 h)",
            "icon": "mdi:alert-octagram", "vertical": True, "visibility": _warn_visible(s)}
    if tap:
        card["tap_action"] = tap
    return card


def warn_markdown(s: str) -> dict[str, Any]:
    e = f"sensor.{s}_weather_warning_next_24_hours"
    return {"type": "markdown", "visibility": _warn_visible(s), "content":
            "{% for w in state_attr('" + e + "','warnings') or [] %}"
            "{% set on = w.onset|as_datetime|as_local %}{% set off = w.expires|as_datetime|as_local %}"
            "<ha-alert alert-type=\"{{ 'error' if w.level == 'red' else 'warning' }}\" title=\"{{ w.event }} · {{ w.level }}\">"
            "{{ w.region }} · {{ ('until ' ~ off.strftime('%a %H:%M')) if on <= now() else "
            "('from ' ~ on.strftime('%a %H:%M') ~ ' to ' ~ off.strftime('%a %H:%M')) }}<br>"
            "{{ w.description | replace('\\n', '<br>') }}</ha-alert>"
            "{% endfor %}"}


# ── sections ────────────────────────────────────────────────────────────────
def overview_section(loc: dict[str, Any]) -> dict[str, Any]:
    t = nav(loc["path"])
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": loc["title"], "heading_style": "title", "icon": loc["icon"], "tap_action": t,
         "badges": [{"type": "entity", "entity": sensor(loc, "temperature"), "show_state": True,
                     "show_icon": True, "tap_action": t}]},
        {"type": "weather-forecast", "entity": loc["weather"], "forecast_type": "daily", "show_current": True,
         "show_forecast": True, "tap_action": t},
        warn_tile(slug(loc), t),
        *([cam(loc["cams"][0], tap_action={"action": "more-info"})] if loc.get("cams") else []),
        tile(sensor(loc, "wind_speed"), "Wind", tap_action=t),
        tile(sensor(loc, "wind_speed_max"), "Gusts", tap_action=t),
        tile(radar(slug(loc), "rain_rate"), "Rain now", tap_action=t),
        tile(radar(slug(loc), "rain_last_hour"), "Rain last hour", tap_action=t),
        tile(sensor(loc, "humidity"), "Humidity", tap_action=t),
        hail_tile(slug(loc), tap_action=t),
        *([tile(f"sensor.slf_avalanche_danger_level_{loc['slf']}", "Avalanche danger", tap_action=t)]
          if loc.get("slf") else []),
        *([tile(f"sensor.slf_imis_{loc['imis'][0]}_snow_height", f"Snow {IMIS[loc['imis'][0]]['name']} (measured)",
                icon="mdi:snowflake", tap_action=t)] if loc.get("imis") else []),
        *[tile(f"sensor.{k}_snow_mountain", f"{n} snow", icon="mdi:snowflake", tap_action=t)
          for k, n in loc.get("ski", [])],
        details_button(loc["title"], t),
    ]}


def compare_section() -> dict[str, Any]:
    def g(entities: list[str], title: str, columns: int) -> dict[str, Any]:
        return dict(hist(entities, title), grid_options={"columns": columns})
    return {"type": "grid", "column_span": 4, "cards": [
        {"type": "heading", "heading": "Compare locations", "heading_style": "title", "icon": "mdi:compare-horizontal"},
        g([sensor(l, "temperature") for l in LOCATIONS], "Temperature (48 h)", 12),
        g([sensor(l, "wind_speed_max") for l in LOCATIONS], "Gusts (48 h)", 6),
        g([radar(slug(l), "rain_rate") for l in LOCATIONS], "Rain rate, radar (48 h)", 6),
        g([sensor(l, "sun_irradiation") for l in LOCATIONS], "Irradiation (48 h)", 6),
        g([sensor(l, "pressure_qnh") for l in LOCATIONS], "Pressure QNH (48 h)", 6),
    ]}


def snow_legend() -> str:
    return ("**Fresh snow, from (cm)**\n\n"
            + "| " + " | ".join(f'<font color="{c}">██</font>' for c, _ in SNOW_SCALE) + " |\n"
            + "|" + ":-:|" * len(SNOW_SCALE) + "\n"
            + "| " + " | ".join(str(v) for _, v in SNOW_SCALE) + " |\n\n"
            + "<small>The scale repeats: yellow and orange appear twice (1 / 50 cm and 10 / 70 cm) — check the "
              "neighbouring colours. Blue-grey shading is rain (1–40+ l/m²). Day maps cover 24 h from 07:00; "
              "the 48–144 h maps are totals from today 07:00. Andermatt lies just west of Disentis/Mustér. "
              "Source: GeoSphere Austria / bergfex.</small>")


def ski_sections(loc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for k, name in loc.get("ski", []):
        def e(x: str) -> str:
            return f"sensor.{k}_{x}"
        out.append({"type": "grid", "cards": [
            {"type": "heading", "heading": f"Ski area {name}", "icon": "mdi:ski",
             "badges": [{"type": "entity", "entity": e("status"), "show_state": True, "show_icon": True}]},
            tile(e("snow_mountain"), "Snow mountain", icon="mdi:image-filter-hdr"),
            tile(e("snow_valley"), "Snow valley", icon="mdi:home-variant"),
            tile(e("new_snow"), "New snow", icon="mdi:snowflake-alert"),
            tile(e("last_snowfall"), "Last snowfall", icon="mdi:calendar-clock"),
            tile(e("snow_condition"), "Snow", icon="mdi:snowflake-variant"),
            tile(e("slope_condition"), "Slopes", icon="mdi:ski"),
            tile(e("lifts_open_count"), "Lifts open", icon="mdi:gondola"),
            tile(e("slopes_open_km"), "Slopes open", icon="mdi:map-marker-distance"),
            tile(e("avalanche_warning"), "Avalanche", icon="mdi:alert"),
            tile(e("status"), "Season", icon="mdi:calendar-range",
                 state_content=["state", "winter_season_start", "winter_season_end"]),
            tile(e("last_update"), "Report updated", icon="mdi:update"),
            hist([e("snow_mountain"), e("snow_valley")], "Snow depth (30 days)", 720)]})
    if loc.get("ski"):
        # Bergfex's maps cover the whole country and are identical for every
        # resort, so one resort's set is enough.
        k = loc["ski"][0][0]
        days = ["today", "tomorrow", "day 3", "day 4", "day 5", "day 6"]
        out.append({"type": "grid", "column_span": 2, "cards": [
            {"type": "heading", "heading": "Snow forecast Switzerland (bergfex)", "icon": "mdi:map"},
            {"type": "markdown", "grid_options": {"columns": 12}, "content": snow_legend()},
            cam(f"image.{k}_summary_image_48h", name="Fresh snow – next 48 h", grid_options={"columns": 12}),
            *[cam(f"image.{k}_summary_image_{h}h", name=f"Next {h} h", grid_options={"columns": 3})
              for h in (72, 96, 120, 144)],
            *[cam(f"image.{k}_forecast_image_day_{d}", name=f"24 h from 07:00 {days[d]}", grid_options={"columns": 4})
              for d in range(6)]]})
    return out


def slf_section(sfx: str) -> dict[str, Any]:
    def e(x: str) -> str:
        return f"sensor.slf_avalanche_{x}_{sfx}"
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": "Avalanche bulletin (SLF)", "icon": "mdi:alert-octagon-outline"},
        tile(e("danger_level"), "Danger level", state_content=["state", "valid_to"]),
        tile(e("region"), "Warning region"),
        *[tile(e(f"problem_{i}"), f"Problem {i}") for i in (1, 2, 3)],
        {"type": "markdown", "content":
            "{% set s = '" + e("danger_level") + "' %}{% if state_attr(s,'active') %}{{ state_attr(s,'danger_text') }}"
            "\n\n<small>Published {{ state_attr(s,'publication_time') }} · next update {{ state_attr(s,'next_update') }}"
            "</small>{% else %}No bulletin issued for {{ state_attr(s,'region') }} at the moment.{% endif %}"},
        hist([e("danger_level")], "Danger level (30 days)", 720)]}


def imis_section(sfx: str) -> dict[str, Any]:
    station = IMIS[sfx]
    pre = f"sensor.slf_imis_{sfx}_"
    have = station["sensors"]
    cards = [{"type": "heading", "heading": f"IMIS {station['name']} · {station['elevation']} m", "icon": "mdi:antenna"}]
    cards += [tile(pre + k, IMIS_NAMES[k]) for k in have]
    if "snow_height" in have:
        cards.append(hist([pre + "snow_height"], "Snow depth (30 days)", 720))
    cards.append(hist([pre + k for k in ("air_temperature", "snow_surface_temperature") if k in have],
                      "Temperature (72 h)", 72))
    cards.append(hist([pre + k for k in ("wind_speed", "wind_gust") if k in have], "Wind & gusts (48 h)"))
    return {"type": "grid", "cards": cards}


def normals_section(loc: dict[str, Any]) -> dict[str, Any]:
    """Today and this month against the station's 1991-2020 normals."""
    def e(key: str) -> str:
        return sensor(loc, key)
    record = e("record_high_for_the_date")
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": "Compared to normal (1991–2020)", "icon": "mdi:chart-bell-curve"},
        tile(e("high_vs_normal"), "Today's high", state_content=["state", "high", "normal_high"]),
        tile(e("low_vs_normal"), "Tonight's low", state_content=["state", "low", "normal_low"]),
        tile(record, "Record high", state_content=["state", "year"]),
        tile(record, "Record low", icon="mdi:thermometer-low", state_content=["record_low", "record_low_year"]),
        tile(e("month_vs_normal"), "Month", state_content=["state", "mean", "normal_mean"]),
        tile(e("month_s_rain_vs_normal"), "Month's rain", icon="mdi:weather-rainy",
             state_content=["state", "rain", "normal_rain"]),
        tile(e("month_s_sunshine_vs_normal"), "Month's sunshine", icon="mdi:weather-sunny",
             state_content=["state", "sunshine", "normal_sunshine"]),
        hist([e("high_vs_normal"), e("low_vs_normal")], "Day against normal (30 days)", 720)]}


def foehn_section(loc: dict[str, Any]) -> dict[str, Any]:
    """MeteoSwiss's measured Föhn index, and the outlook from the pressure across the Alps."""
    s = slug(loc)
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": "Föhn", "icon": "mdi:weather-windy-variant"},
        tile(sensor(loc, "fohn"), "Föhn index (measured)", icon="mdi:weather-windy"),
        tile(f"sensor.{s}_fohn_outlook", "Outlook", icon="mdi:crystal-ball"),
        tile(f"sensor.{s}_fohn_pressure_difference", "Lugano − Kloten", icon="mdi:gauge"),
        {"type": "markdown", "content": "<small>South föhn from 4 hPa more pressure in Lugano than Kloten, strong "
                                        "from 8. Negative values mean north föhn (Ticino side).</small>"},
        hist([f"sensor.{s}_fohn_pressure_difference"], "Pressure difference (48 h)"),
        hist([sensor(loc, "fohn")], "Föhn index (48 h)")]}


def pollen_section(station: str, prefix: str) -> dict[str, Any]:
    """Hourly concentrations (pollen/m³) from the MeteoSwiss pollen station."""
    def e(kind: str) -> str:
        return f"sensor.{prefix}_{kind}"
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": f"Pollen ({station})", "icon": "mdi:flower-pollen"},
        *[tile(e(k), k.capitalize(), icon="mdi:flower-pollen") for k in POLLEN_TYPES],
        {"type": "markdown", "content": "<small>Hourly pollen/m³. MeteoSwiss's 'strong' class starts at 70 for hazel, "
                                        "alder and birch, 50 for grasses, 100 for ash (daily means).</small>"},
        hist([e("birch"), e("grasses"), e("hazel")], "Birch, grasses, hazel (7 days)", 168)]}


def lightning_section(name: str) -> dict[str, Any]:
    """Blitzortung: strikes within its radius (100 km) over its time window (2 h)."""
    def e(x: str) -> str:
        return f"sensor.{name}_lightning_{x}"
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": "Lightning (Blitzortung)", "icon": "mdi:weather-lightning"},
        tile(e("counter"), "Strikes (100 km, 2 h)", icon="mdi:flash"),
        tile(e("distance"), "Last strike", icon="mdi:map-marker-distance"),
        tile(e("azimuth"), "Direction", icon="mdi:compass-outline"),
        hist([e("counter")], "Strikes (48 h)")]}


def river_entity(river: dict[str, Any], condition: str) -> str:
    return f"sensor.{river['slug']}_{condition}"


def danger_level(river: dict[str, Any]) -> str:
    """Template: FOEN's flood danger level (1-5) for the current discharge."""
    return ("{% set q = states('" + river_entity(river, "discharge") + "')|float(0) %}"
            "{% set ns = namespace(l=1) %}{% for t in " + str(river["danger"]) + " %}"
            "{% if q >= t %}{% set ns.l = loop.index + 1 %}{% endif %}{% endfor %}{{ ns.l }}")


def river_trend(river: dict[str, Any]) -> str:
    """Rising, falling or steady: now against the 24-hour mean (FOEN's own attribute)."""
    main = river["conditions"][0]
    e = river_entity(river, main)
    if main == "level":  # a lake: centimetres, not percent
        return ("{% set d = (states('" + e + "')|float(0) - state_attr('" + e + "','mean_24h')|float(0)) * 100 %}"
                "<small>{{ '↗ rising' if d >= 2 else ('↘ falling' if d <= -2 else '→ steady') }} "
                "({{ d|round(0)|int }} cm against the 24 h mean)</small>")
    return ("{% set q = states('" + e + "')|float(0) %}{% set m = state_attr('" + e + "','mean_24h')|float(0) %}"
            "{% set p = ((q / m - 1) * 100) if m > 0 else 0 %}"
            "<small>{{ '↗ rising' if p >= 10 else ('↘ falling' if p <= -10 else '→ steady') }} "
            "({{ '+' if p > 0 }}{{ p|round(0)|int }} % against the 24 h mean of {{ m|round(1) }} m³/s)</small>")


def rivers_section() -> dict[str, Any]:
    cards = [{"type": "heading", "heading": "Rivers (FOEN)", "heading_style": "title", "icon": "mdi:waves"}]
    for r in RIVERS:
        cards.append({"type": "heading", "heading": r["title"], "heading_style": "subtitle", "icon": "mdi:waves-arrow-up"})
        names = {"discharge": "Discharge", "level": "Water level", "temperature": "Water temperature"}
        cards += [tile(river_entity(r, c), names[c], state_content=["state", "max_24h"]) if c == "discharge"
                  else tile(river_entity(r, c), names[c]) for c in r["conditions"]]
        cards.append({"type": "markdown", "content": river_trend(r)})
        if r.get("danger"):
            cards.append({"type": "markdown", "content":
                "<small>Flood danger level " + danger_level(r) +
                " · level 2 from " + str(r["danger"][0]) + " m³/s · yearly mean " + str(r["mean"]) + " m³/s</small>"})
        main = r["conditions"][0]  # discharge, or level for a lake
        cards.append(dict(hist([river_entity(r, main)], f"{r['title']} {main} (7 days)", 168),
                          grid_options={"columns": 12}))
    return {"type": "grid", "column_span": 4, "cards": cards}


def forecast_cards(w: str) -> list[dict[str, Any]]:
    return [{"type": "heading", "heading": "Hourly forecast", "icon": "mdi:clock-outline"},
            {"type": "weather-forecast", "entity": w, "forecast_type": "hourly", "show_current": False,
             "show_forecast": True}]


# ── views ───────────────────────────────────────────────────────────────────
def location_view(loc: dict[str, Any]) -> dict[str, Any]:
    w = loc["weather"]
    return {"title": loc["title"], "path": loc["path"], "icon": loc["icon"], "type": "sections", "max_columns": 4,
            "subview": True, "back_path": f"{BASE}/overview", "sections": [
        {"type": "grid", "cards": [
            {"type": "heading", "heading": f"{loc['title']} – now", "heading_style": "title",
             "icon": "mdi:weather-partly-cloudy"},
            {"type": "markdown", "content": f"<small>Station: {loc['stations_text']}</small>"},
            warn_markdown(slug(loc)),
            {"type": "weather-forecast", "entity": w, "forecast_type": "daily", "show_current": True,
             "show_forecast": False},
            tile(sensor(loc, "temperature"), "Temperature"), tile(sensor(loc, "dew_point"), "Dew point"),
            tile(sensor(loc, "humidity"), "Humidity"), tile(sensor(loc, "pressure_qnh"), "Pressure (QNH)"),
            *([tile(f"sensor.{slug(loc)}_freezing_level", "Freezing level", icon="mdi:snowflake-thermometer")]
              if loc.get("freezing") else [])]},
        *([{"type": "grid", "column_span": 2, "cards": [
            {"type": "heading", "heading": "Webcams", "icon": "mdi:webcam"},
            *[cam(c, grid_options={"columns": 12}) for c in loc["cams"]]]}] if loc.get("cams") else []),
        *([slf_section(loc["slf"])] if loc.get("slf") else []),
        *ski_sections(loc),
        *[imis_section(x) for x in loc.get("imis", [])],
        *([lightning_section(loc["lightning"])] if loc.get("lightning") else []),
        normals_section(loc),
        *([foehn_section(loc)] if loc.get("foehn") else []),
        *([pollen_section(*loc["pollen"])] if loc.get("pollen") else []),
        {"type": "grid", "cards": [
            *forecast_cards(w),
            {"type": "heading", "heading": "Daily forecast", "icon": "mdi:calendar-week"},
            {"type": "weather-forecast", "entity": w, "forecast_type": "daily", "show_current": False,
             "show_forecast": True}]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": "Wind", "icon": "mdi:weather-windy"},
            gauge(sensor(loc, "wind_speed"), "Wind", 100, [0, 30, 60, 90]),
            gauge(sensor(loc, "wind_speed_max"), "Gusts", 150, [0, 50, 80, 110]),
            tile(sensor(loc, "wind_direction"), "Direction", icon="mdi:compass-outline"),
            hist([sensor(loc, "wind_speed"), sensor(loc, "wind_speed_max")], "Wind & gusts (48 h)")]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": "Sun, rain & hail", "icon": "mdi:weather-sunny"},
            radar_loop(slug(loc)),
            tile(sensor(loc, "sun_irradiation"), "Irradiation"), tile(sensor(loc, "10_minute_sun"), "Sun (10 min)"),
            *radar_cards(slug(loc)),
            tile(loc["rain"], f"Rain 10 min ({loc['rain_station']})"),
            {"type": "markdown", "content": "<small>Radar: MeteoSwiss's weather radar every 5 minutes, over this "
                                            "place's square kilometre. It sees rain start first. The rain of the last "
                                            "hour is the radar adjusted to the rain gauges (CombiPrecip); "
                                            f"the {loc['rain_station']} station's 10-minute total is measured.</small>"},
            hist([sensor(loc, "sun_irradiation")], "Irradiation (48 h)"),
            hist([radar(slug(loc), "rain_rate")], "Rain rate, radar (48 h)"),
            hist([radar(slug(loc), "rain_last_hour")], "Rain last hour, radar (48 h)"),
            hist([radar(slug(loc), "hail_probability")], "Hail chance, radar (48 h)"),
            hist([loc["rain"]], f"Rain per 10 min, {loc['rain_station']} (48 h)")]},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": "Trends", "icon": "mdi:chart-line"},
            hist([sensor(loc, "temperature"), sensor(loc, "dew_point")], "Temperature & dew point", 72),
            hist([sensor(loc, "humidity")], "Humidity", 72),
            hist([sensor(loc, "pressure_qnh"), sensor(loc, "pressure_qff")], "Pressure", 72)]},
    ]}


def _mountain(m: dict[str, Any]) -> dict[str, Any]:
    return dict(m, path=f"mtn-{m['slug'].replace('_', '-')}", weather=f"weather.{m['slug']}",
                freezing=f"sensor.{m['slug']}_freezing_level")


def mountain_section(m: dict[str, Any]) -> dict[str, Any]:
    m = _mountain(m)
    t = nav(m["path"])
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": f"{m['title']} · {m['elevation']} m", "heading_style": "title",
         "icon": m["icon"], "tap_action": t},
        {"type": "weather-forecast", "entity": m["weather"], "forecast_type": "daily", "show_current": True,
         "show_forecast": True, "tap_action": t},
        warn_tile(m["slug"], t),
        tile(m["freezing"], "Freezing level", tap_action=t),
        tile(radar(m["slug"], "rain_rate"), "Precipitation now", tap_action=t),
        hail_tile(m["slug"], tap_action=t),
        tile(m["weather"], "Wind / gusts", icon="mdi:weather-windy", state_content=["wind_speed", "wind_gust_speed"],
             tap_action=t),
        *([tile(f"sensor.slf_imis_{m['imis']}_air_temperature", "Measured temp", tap_action=t),
           tile(f"sensor.slf_imis_{m['imis']}_wind_gust", "Measured gusts", tap_action=t)] if m.get("imis") else []),
        details_button(m["title"], t),
    ]}


def mountain_view(m: dict[str, Any]) -> dict[str, Any]:
    m = _mountain(m)
    w = m["weather"]
    return {"title": m["title"], "path": m["path"], "icon": m["icon"], "type": "sections", "max_columns": 3,
            "subview": True, "back_path": f"{BASE}/overview", "sections": [
        {"type": "grid", "cards": [
            {"type": "heading", "heading": f"{m['title']} · {m['elevation']} m", "heading_style": "title",
             "icon": m["icon"]},
            {"type": "markdown",
             "content": "<small>Forecast for the summit altitude; current conditions are forecast, not measured, "
                        "except the radar's precipitation and hail over the summit.</small>"},
            warn_markdown(m["slug"]),
            {"type": "weather-forecast", "entity": w, "forecast_type": "daily", "show_current": True,
             "show_forecast": False},
            tile(m["freezing"], "Freezing level"),
            tile(w, "Temperature", icon="mdi:thermometer", state_content=["temperature"]),
            tile(w, "Wind / gusts", icon="mdi:weather-windy", state_content=["wind_speed", "wind_gust_speed"]),
            tile(w, "Cloud cover", icon="mdi:weather-cloudy", state_content=["cloud_coverage"]),
            radar_loop(m["slug"]),
            *radar_cards(m["slug"]),
            hist([m["freezing"]], "Freezing level (72 h)", 72),
            hist([radar(m["slug"], "rain_rate")], "Precipitation rate, radar (48 h)")]},
        *([imis_section(m["imis"])] if m.get("imis") else []),
        {"type": "grid", "cards": forecast_cards(w)},
        {"type": "grid", "cards": [
            {"type": "heading", "heading": "Daily forecast", "icon": "mdi:calendar-week"},
            {"type": "weather-forecast", "entity": w, "forecast_type": "daily", "show_current": False,
             "show_forecast": True}]},
    ]}


def overview() -> dict[str, Any]:
    return {"title": "Overview", "path": "overview", "icon": "mdi:weather-partly-cloudy", "type": "sections",
            "max_columns": 4, "sections": [
        *[overview_section(l) for l in LOCATIONS],
        compare_section(),
        rivers_section(),
        {"type": "grid", "column_span": 4, "cards": [
            {"type": "heading", "heading": "Mountains & passes", "heading_style": "title",
             "icon": "mdi:image-filter-hdr"}]},
        *[mountain_section(m) for m in MOUNTAINS],
        {"type": "grid", "column_span": 4, "cards": [
            dict(hist([_mountain(m)["freezing"] for m in MOUNTAINS], "Freezing level (72 h)", 72),
                 grid_options={"columns": 12})]},
    ]}


def build() -> dict[str, Any]:
    return {"views": [overview(), *[location_view(l) for l in LOCATIONS], *[mountain_view(m) for m in MOUNTAINS]]}
