"""Turns `pills.py` into the Mobile dashboard's alert row and Alerts sub-page.

Pure functions over plain dicts, so the tests can run them without Home
Assistant: `apply(dashboard)` takes the dashboard config as HA returns it and
gives back the config with the alert row and sub-page in place, everything else
untouched.

The row is a Mushroom chips card. Mushroom wraps chips onto a second line and
card-mod isn't installed, so the row instead has a fixed number of places:
place i shows the i-th active pill's icon, and the last place turns into "+N"
when more pills are active than there are places.
"""
from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_pills = runpy.run_path(str(HERE / "pills.py"))
ALERTS: list[dict[str, Any]] = _pills["ALERTS"]
GROUPS: list[str] = _pills["GROUPS"]
UPDATES: str = _pills["UPDATES"]
LOWBAT_LIST: str = _pills["LOWBAT_LIST"]

DASHBOARD = "dashboard-mobile"
SUBVIEW = "weather-alerts"
COUNT = "sensor.weather_alerts_active"
# Icons that fit one phone-width row (36 px chips, 8 px apart).
PLACES = 6
NAV = {"action": "navigate", "navigation_path": f"/{DASHBOARD}/{SUBVIEW}"}
GROUP_ICONS = {
    "Safety": "mdi:shield-home-outline", "Kitchen": "mdi:fridge-outline",
    "Forecast": "mdi:crystal-ball", "Weather now": "mdi:weather-partly-cloudy",
    "Mountains": "mdi:image-filter-hdr", "Home": "mdi:home-outline",
    "Calendar": "mdi:calendar-star", "Maintenance": "mdi:wrench-outline",
}


def entity(pill: dict[str, Any]) -> str:
    return f"binary_sensor.pill_{pill['key']}"


def count_states() -> list[str]:
    """Every value the count helper can take while at least one pill is on.

    Mushroom's conditional chip matches states, not ranges, so "1 or more" is
    written as the explicit list. A few spare values cover pills added later
    before this file is rebuilt.
    """
    return [str(n) for n in range(1, len(ALERTS) + 11)]


def _cond(states: list[str]) -> list[dict[str, Any]]:
    return [{"condition": "state", "entity": COUNT, "state": states}]


_ACTIVE = (
    "{% set ns = namespace(a=[]) %}{% for k in "
    + json.dumps([p["key"] for p in ALERTS])
    + " %}{% if is_state('binary_sensor.pill_' ~ k, 'on') %}"
    "{% set ns.a = ns.a + [k] %}{% endif %}{% endfor %}"
)


def _pick(index: int, field: str) -> str:
    """Template for the icon or colour of the index-th active pill."""
    table = json.dumps({p["key"]: p[field] for p in ALERTS})
    return (_ACTIVE + "{% set m = " + table + " %}"
            "{{ m[ns.a[" + str(index) + "]] if ns.a|count > " + str(index) + " else '' }}")


def chips() -> list[dict[str, Any]]:
    states = count_states()

    def place(index: int, shown_for: list[str]) -> dict[str, Any]:
        return {"type": "conditional", "conditions": _cond(shown_for),
                "chip": {"type": "template", "icon": _pick(index, "icon"),
                         "icon_color": _pick(index, "color"), "tap_action": NAV}}

    # Places 0..PLACES-2 show whenever at least index+1 pills are on.
    row = [place(i, states[i:]) for i in range(PLACES - 1)]
    # The last place is an icon only when exactly PLACES pills are on...
    row.append(place(PLACES - 1, [str(PLACES)]))
    # ...and "+N" (the pills that didn't get a place) when there are more.
    row.append({"type": "conditional", "conditions": _cond(states[PLACES:]),
                "chip": {"type": "template", "icon": "",
                         "content": "+{{ states('" + COUNT + "')|int - " + str(PLACES - 1) + " }}",
                         "tap_action": NAV}})
    return row


def row_card() -> dict[str, Any]:
    return {"type": "custom:mushroom-chips-card", "alignment": "center", "chips": chips(),
            "visibility": _cond(count_states())}


def is_row_card(card: dict[str, Any]) -> bool:
    return (card.get("type") == "custom:mushroom-chips-card"
            and any(c.get("entity") == COUNT for c in card.get("visibility", [])))


def _tile(entity_id: str, name: str) -> dict[str, Any]:
    return {"type": "tile", "entity": entity_id, "name": name, "vertical": True}


def subview() -> dict[str, Any]:
    active = [
        {"type": "heading", "heading": "Active now", "heading_style": "title", "icon": "mdi:bell-ring-outline"},
        {"type": "markdown", "content": "All quiet: nothing needs your attention right now.",
         "visibility": [{"condition": "state", "entity": COUNT, "state": "0"}]},
    ]
    for p in ALERTS:
        active.append({
            "type": "custom:mushroom-template-card", "entity": entity(p),
            "primary": p["name"], "secondary": p["secondary"], "icon": p["icon"], "icon_color": p["color"],
            "multiline_secondary": True, "fill_container": True, "grid_options": {"columns": 12},
            "tap_action": {"action": "more-info"},
            "visibility": [{"condition": "state", "entity": entity(p), "state": "on"}],
        })
    sections = [{"type": "grid", "column_span": 2, "cards": active}]
    for group in GROUPS:
        cards = [{"type": "heading", "heading": group, "heading_style": "title", "icon": GROUP_ICONS[group]}]
        for p in (p for p in ALERTS if p["group"] == group):
            cards.append({"type": "heading", "heading": p["name"], "heading_style": "subtitle", "icon": p["icon"],
                          "badges": [{"type": "entity", "entity": entity(p), "show_state": True,
                                      "show_icon": False, "color": p["color"]}]})
            cards.append({"type": "markdown", "content": f"<small>{p['rule']}</small>"})
            cards += [_tile(e, n) for e, n in p["data"]]
            if p["key"] == "updates_waiting":
                cards.append({"type": "markdown", "content":
                              "{{ " + UPDATES + " | map(attribute='name') | join(', ') or 'Everything is up to date.' }}"})
            if p["key"] == "low_batteries":
                cards.append({"type": "markdown", "content": LOWBAT_LIST})
            if p["hist"]:
                cards.append({"type": "history-graph", "hours_to_show": 48,
                              "entities": [{"entity": e} for e in p["hist"]]})
        sections.append({"type": "grid", "cards": cards})
    sections.append({"type": "grid", "column_span": 2, "cards": [{
        "type": "button", "name": "Open the Weather dashboard", "icon": "mdi:sun-snowflake", "show_state": False,
        "tap_action": {"action": "navigate", "navigation_path": "/dashboard-weather/overview"},
        "grid_options": {"columns": 12, "rows": 1}}]})
    return {"title": "Alerts", "path": SUBVIEW, "icon": "mdi:bell-ring-outline", "type": "sections",
            "max_columns": 2, "subview": True, "back_path": f"/{DASHBOARD}/0", "sections": sections}


def apply(dashboard: dict[str, Any]) -> dict[str, Any]:
    """The dashboard with the alert row and sub-page replaced or added.

    The row goes right after the weather chips card at the top of the first
    view's first section. That card itself is never changed.
    """
    out = copy.deepcopy(dashboard)
    cards = out["views"][0]["sections"][0]["cards"]
    cards[:] = [c for c in cards if not is_row_card(c)]
    weather = cards[0]
    if weather.get("type") != "custom:mushroom-chips-card" or not all(
            c.get("type") == "weather" for c in weather.get("chips", [])):
        raise ValueError("the first card of the Mobile dashboard is no longer the weather chips row")
    cards.insert(1, row_card())
    out["views"] = [v for v in out["views"] if v.get("path") != SUBVIEW] + [subview()]
    return out
