"""Denise's dashboard (`dashboard-denise`): her default, set in her profile.

Denise lives in Altdorf too, not here, so the page is about the town and the
road out of it, and has no controls for any room:

- her own set of alert pills (`PILLS`, keys from `mobile-alerts/pills.py`),
  as a row of icons and an Alerts sub-page;
- the weather in Altdorf, with the Föhn index and outlook;
- the Axenstrasse: open or closed, traffic flowing, the closures to come
  (its calendar) and the traffic each way.

The cards come from the Weather and Infrastructure builders, so a renamed
entity is fixed in one place. `build()` returns the whole config, owned by the
script like the other dashboards: a card added in the UI is gone after the
next sync.

Her pills are the same `binary_sensor.pill_<key>` the integration makes for
the Mobile dashboard, so a pill switched off there (Choose alerts) is gone
here too. Dismissing is shared as well, so her cards have no hold action, and
a pill Jan dismissed still shows for her. Her row shows one chip per pill
instead of the Mobile dashboard's slots: with a short list, few are on at once.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"{name.replace('-', '_')}_build", HERE.parent / name / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


weather = _load("weather")
roads = _load("infrastructure")
alerts = _load("mobile-alerts")

DASHBOARD = "dashboard-denise"
TITLE = "Denise"
ICON = "mdi:cat"
VIEW = "home"
SUBVIEW = "alerts"
NAV = {"action": "navigate", "navigation_path": f"/{DASHBOARD}/{SUBVIEW}"}

# Her pills: the town's weather, föhn, the roads out, the rivers and lake, the
# calendar. Nothing about this flat (doors, fridge, servers, the VPN). They
# show in pills.py's order, not this one.
PILLS = {
    "weather_warning", "hail", "downpour", "lightning_nearby", "raining_now", "rain_next_hour",
    "snow_in_altdorf", "snow_coming", "ground_frost", "frost_tonight",
    "fohn_altdorf", "fohn_coming", "sun_above_the_fog", "pollen_high",
    "axenstrasse_closed", "gotthard_tunnel_closed", "gotthard_jam",
    "schachen_spate", "lake_high", "holiday_tomorrow", "record_warm", "record_cold",
}
ALTDORF = next(loc for loc in weather.LOCATIONS if loc["path"] == "altdorf")
AXEN_CALENDAR = "calendar.national_roads_axenstrasse"
# Full screen: kiosk-mode (HACS) hides the header and the sidebar. Her Alerts
# page has its own back chip, so nothing needs the header. To edit the page in
# the UI, open it with ?disable_km on the URL.
KIOSK = {"hide_header": True, "hide_sidebar": True}
AXEN_STATION = "a4_sisikon_axenstrasse"


def pills() -> list[dict[str, Any]]:
    return [p for p in alerts.ALERTS if p["key"] in PILLS]


def _on(pill: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"condition": "state", "entity": alerts.entity(pill), "state": "on"}]


def _quiet() -> dict[str, Any]:
    return {"type": "markdown", "content": "All quiet: nothing needs your attention right now.",
            "visibility": [{"condition": "state", "entity": alerts.entity(p), "state_not": "on"} for p in pills()]}


def chips_card() -> dict[str, Any]:
    """One chip per pill, shown while it's on; tapping opens the Alerts page."""
    def chip(p: dict[str, Any]) -> dict[str, Any]:
        e = alerts.entity(p)
        return {"type": "conditional", "conditions": _on(p),
                "chip": {"type": "template", "icon": p["icon"], "icon_color": "{{ state_attr('" + e + "', 'color') }}",
                         "content": "{{ state_attr('" + e + "', 'content') or '' }}", "tap_action": NAV}}
    return {"type": "custom:mushroom-chips-card", "alignment": "center", "chips": [chip(p) for p in pills()]}


def alerts_section() -> dict[str, Any]:
    return {"type": "grid", "column_span": 2, "cards": [
        {"type": "heading", "heading": "Alerts", "heading_style": "title", "icon": "mdi:bell-ring-outline",
         "tap_action": NAV},
        chips_card(), _quiet()]}


def weather_section() -> dict[str, Any]:
    loc, s = ALTDORF, weather.slug(ALTDORF)
    t = weather.nav(loc["path"])
    return {"type": "grid", "cards": [
        {"type": "heading", "heading": "Weather in Altdorf", "heading_style": "title", "icon": loc["icon"],
         "tap_action": t, "badges": [{"type": "entity", "entity": weather.sensor(loc, "temperature"),
                                      "show_state": True, "show_icon": True}]},
        weather.warn_markdown(s),
        {"type": "weather-forecast", "entity": loc["weather"], "forecast_type": "daily", "show_current": True,
         "show_forecast": True},
        weather.today_heading(s),
        weather.tile(weather.sensor(loc, "wind_speed"), "Wind", grid_options={"columns": 6}),
        weather.tile(weather.sensor(loc, "wind_speed_max"), "Gusts", grid_options={"columns": 6}),
        weather.tile(weather.radar(s, "rain_rate"), "Rain now", grid_options={"columns": 6}),
        weather.tile(weather.sensor(loc, "humidity"), "Humidity", grid_options={"columns": 6}),
        weather.hail_tile(s, grid_options={"columns": 6}),
        *weather.forecast_cards(loc["weather"]),
        {"type": "button", "name": "More weather", "icon": "mdi:open-in-app", "show_state": False,
         "tap_action": t, "grid_options": {"columns": 12, "rows": 1}},
    ]}


def foehn_section() -> dict[str, Any]:
    return weather.foehn_section(ALTDORF)


def axenstrasse_section() -> dict[str, Any]:
    """Status, the next closure and the note from the Roads view, then what's
    counted at Sisikon each way and the closures to come."""
    def counted(direction: str, kind: str, name: str) -> dict[str, Any]:
        return roads.tile(roads.station(AXEN_STATION, direction, kind), name, 6)
    status = roads.axenstrasse_section()["cards"]
    return {"type": "grid", "cards": [
        *status,
        roads.heading("Traffic at Sisikon", "mdi:car-multiple", "subtitle"),
        counted("south", "traffic", "Towards Altdorf"), counted("north", "traffic", "Towards Brunnen"),
        counted("south", "speed", "Speed towards Altdorf"), counted("north", "speed", "Speed towards Brunnen"),
        roads.heading("Closures to come", "mdi:calendar-alert", "subtitle"),
        {"type": "calendar", "initial_view": "listWeek", "entities": [AXEN_CALENDAR],
         "grid_options": {"columns": "full", "rows": 6}},
        {"type": "statistics-graph", "title": "Vehicles per hour, last 7 days", "stat_types": ["mean"],
         "period": "hour", "days_to_show": 7, "chart_type": "line", "grid_options": {"columns": "full"},
         "entities": [{"entity": roads.station(AXEN_STATION, "south", "traffic"), "name": "Towards Altdorf"},
                      {"entity": roads.station(AXEN_STATION, "north", "traffic"), "name": "Towards Brunnen"}]},
    ]}


def _card(p: dict[str, Any]) -> dict[str, Any]:
    e = alerts.entity(p)
    return {"type": "custom:mushroom-template-card", "entity": e, "primary": p["name"], "secondary": p["secondary"],
            "icon": p["icon"], "icon_color": "{{ state_attr('" + e + "', 'color') }}", "multiline_secondary": True,
            "fill_container": True, "grid_options": {"columns": 12}, "tap_action": {"action": "more-info"},
            "visibility": _on(p)}


def subview() -> dict[str, Any]:
    """A card per pill while it's on. The rules behind them stay on the Mobile
    dashboard's Alerts page: they're for tuning, not for reading."""
    back = {"type": "custom:mushroom-chips-card", "chips": [{"type": "back"}]}
    return {"title": "Alerts", "path": SUBVIEW, "icon": "mdi:bell-ring-outline", "type": "sections",
            "max_columns": 2, "subview": True, "back_path": f"/{DASHBOARD}/{VIEW}", "sections": [
                {"type": "grid", "column_span": 2, "cards": [
                    back, {"type": "heading", "heading": "Active now", "heading_style": "title",
                           "icon": "mdi:bell-ring-outline"},
                    _quiet(), *map(_card, pills())]}]}


def build() -> dict[str, Any]:
    return {"kiosk_mode": KIOSK, "views": [
        {"title": TITLE, "path": VIEW, "icon": ICON, "type": "sections", "max_columns": 2,
         "sections": [alerts_section(), weather_section(), foehn_section(), axenstrasse_section()]},
        subview()]}
