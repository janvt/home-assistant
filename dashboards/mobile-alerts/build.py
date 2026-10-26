"""Turns `pills.py` into the Mobile dashboard's alert row and Alerts sub-page,
and into the definitions `sync.py` loads into the `alert_pills` integration.

Pure functions over plain dicts, so the tests can run them without Home
Assistant: `apply(dashboard)` takes the dashboard config as HA returns it and
gives back the config with the alert row and sub-page in place, everything else
untouched.

The integration (`custom_components/alert_pills/`) evaluates the pills and
works out the row; the dashboard only draws it. Mushroom wraps chips onto a
second line and card-mod isn't installed, so the row has a fixed number of
chips: chip i shows the i-th slot of `sensor.alert_pills_row` and hides when
there is none. How many slots there are is an option of the integration.
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
CRITICAL: set[str] = _pills["CRITICAL"]
NUMBERS: list[dict[str, Any]] = _pills.get("NUMBERS", [])
STATISTICS: list[dict[str, Any]] = _pills.get("STATISTICS", [])
TEMPLATES: list[dict[str, Any]] = _pills.get("TEMPLATES", [])
HISTORY_STATS: list[dict[str, Any]] = _pills.get("HISTORY_STATS", [])

# The integration's names, read from its own file so the two can't drift.
INTEGRATION = HERE.parents[1] / "custom_components" / "alert_pills"
_const = runpy.run_path(str(INTEGRATION / "const.py"))
DOMAIN: str = _const["DOMAIN"]
COUNT: str = _const["COUNT_ENTITY"]
ROW: str = _const["ROW_ENTITY"]
MAX_PLACES: int = _const["MAX_PLACES"]

DASHBOARD = "dashboard-mobile"
SUBVIEW = "weather-alerts"
NAV = {"action": "navigate", "navigation_path": f"/{DASHBOARD}/{SUBVIEW}"}
# The integration's page; Configure there holds the options.
SETTINGS = {"action": "navigate", "navigation_path": f"/config/integrations/integration/{DOMAIN}"}
GROUP_ICONS = {
    "Safety": "mdi:shield-home-outline", "Kitchen": "mdi:fridge-outline",
    "Travel": "mdi:train", "Rivers": "mdi:waves", "Forecast": "mdi:crystal-ball", "Weather now": "mdi:weather-partly-cloudy",
    "Mountains": "mdi:image-filter-hdr", "Home": "mdi:home-outline",
    "Calendar": "mdi:calendar-star", "Climate": "mdi:chart-bell-curve", "Proxmox": "mdi:server", "Maintenance": "mdi:wrench-outline",
}


def entity(pill: dict[str, Any]) -> str:
    return _const["PILL_ENTITY"].format(key=pill["key"])


def dismissable(pill: dict[str, Any]) -> bool:
    return pill["key"] not in CRITICAL


def color(pill: dict[str, Any]) -> str:
    """The pill's colour: fixed, or the highest warning level of its `color_from` sensors."""
    sources = pill.get("color_from")
    if not sources:
        return pill["color"]
    sources = [sources] if isinstance(sources, str) else sources
    return ("{% set lv = namespace(r=0) %}{% for s in " + json.dumps(sources) + " %}"
            "{% set r = {'yellow': 1, 'orange': 2, 'red': 3}.get(states(s), 0) %}"
            "{% if r > lv.r %}{% set lv.r = r %}{% endif %}{% endfor %}"
            "{{ " + json.dumps([pill["color"], "yellow", "orange", "red"]) + "[lv.r] }}")


def definitions() -> dict[str, Any]:
    """What `sync.py` passes to `alert_pills.load`: only what the integration
    evaluates. The rest of a pill (rule, data, history) is for the Alerts page."""
    pills = []
    for p in ALERTS:
        d = {"key": p["key"], "name": p["name"], "group": p["group"], "icon": p["icon"], "color": color(p),
             "state": p["tmpl"], "critical": p["key"] in CRITICAL}
        if p.get("content"):
            d["content"] = p["content"]
        pills.append(d)
    return {"pills": pills, "groups": GROUPS}


def _slots_from(index: int) -> list[dict[str, Any]]:
    """Visible while the row has more than `index` slots in use.

    Mushroom's conditional chip matches states, not ranges, so "more than i" is
    written as the explicit list.
    """
    return [{"condition": "state", "entity": ROW, "state": [str(n) for n in range(index + 1, MAX_PLACES + 1)]}]


def _slot(index: int, field: str) -> str:
    return ("{% set s = state_attr('" + ROW + "', 'slots') or [] %}"
            "{{ s[" + str(index) + "]." + field + " if s|count > " + str(index) + " else '' }}")


def chips() -> list[dict[str, Any]]:
    return [{"type": "conditional", "conditions": _slots_from(i),
             "chip": {"type": "template", "icon": _slot(i, "icon"), "icon_color": _slot(i, "color"),
                      "content": _slot(i, "content"), "tap_action": NAV}}
            for i in range(MAX_PLACES)]


def row_card() -> dict[str, Any]:
    return {"type": "custom:mushroom-chips-card", "alignment": "center", "chips": chips(),
            "visibility": _slots_from(0)}


def is_row_card(card: dict[str, Any]) -> bool:
    # COUNT: the row from before the integration, replaced on the first sync.
    return (card.get("type") == "custom:mushroom-chips-card"
            and any(c.get("entity") in (ROW, COUNT) for c in card.get("visibility", [])))


def _tile(entity_id: str, name: str) -> dict[str, Any]:
    return {"type": "tile", "entity": entity_id, "name": name, "vertical": True}


BACK = f"/{DASHBOARD}/0"


def back_chips(*extra: dict[str, Any]) -> dict[str, Any]:
    """Mushroom's back chip, the way every other page of this dashboard starts."""
    return {"type": "custom:mushroom-chips-card", "chips": [{"type": "back"}, *extra]}


def subview() -> dict[str, Any]:
    active = [
        back_chips({"type": "template", "icon": "mdi:tune-variant", "content": "Choose alerts", "tap_action": SETTINGS}),
        {"type": "heading", "heading": "Active now", "heading_style": "title", "icon": "mdi:bell-ring-outline"},
        {"type": "markdown", "content": "<small>Hold a card to dismiss it until it clears and comes back; hold "
                                        "again to bring it back. Safety alerts can't be dismissed.</small>"},
        {"type": "markdown", "content": "All quiet: nothing needs your attention right now.",
         "visibility": [{"condition": "state", "entity": COUNT, "state": "0"}]},
    ]
    for p in ALERTS:
        card = {
            "type": "custom:mushroom-template-card", "entity": entity(p),
            "primary": p["name"], "secondary": p["secondary"], "icon": p["icon"],
            # The integration renders the colour, `color_from` included.
            "icon_color": "{{ state_attr('" + entity(p) + "', 'color') }}",
            "multiline_secondary": True, "fill_container": True, "grid_options": {"columns": 12},
            "tap_action": {"action": "more-info"},
            "visibility": [{"condition": "state", "entity": entity(p), "state": "on"}],
        }
        if dismissable(p):
            dismissed = "state_attr('" + entity(p) + "', 'dismissed')"
            card["secondary"] = ("{% if " + dismissed + " %}Dismissed · hold to bring back{% else %}"
                                 + p["secondary"] + "{% endif %}")
            card["icon_color"] = ("{% if " + dismissed + " %}disabled{% else %}"
                                  "{{ state_attr('" + entity(p) + "', 'color') }}{% endif %}")
            card["hold_action"] = {"action": "perform-action", "perform_action": f"{DOMAIN}.toggle_dismiss",
                                   "data": {"key": p["key"]}}
        active.append(card)
    sections = [{"type": "grid", "column_span": 2, "cards": active}]
    for group in GROUPS:
        cards = [{"type": "heading", "heading": group, "heading_style": "title", "icon": GROUP_ICONS[group]}]
        for p in (p for p in ALERTS if p["group"] == group):
            cards.append({"type": "heading", "heading": p["name"], "heading_style": "subtitle", "icon": p["icon"],
                          "badges": [{"type": "entity", "entity": entity(p), "show_state": True,
                                      "show_icon": False, "color": p["color"]}]})  # badges take no template
            cards.append({"type": "markdown", "content": f"<small>{p['rule']}</small>"})
            cards += [_tile(e, n) for e, n in p["data"]]
            if p.get("summary"):
                cards.append({"type": "markdown", "content": p["summary"]})
            if p["hist"]:
                cards.append({"type": "history-graph", "hours_to_show": 48,
                              "entities": [{"entity": e} for e in p["hist"]]})
        sections.append({"type": "grid", "cards": cards})
    sections.append({"type": "grid", "column_span": 2, "cards": [back_chips(
        {"type": "template", "icon": "mdi:sun-snowflake", "content": "Weather",
         "tap_action": {"action": "navigate", "navigation_path": "/dashboard-weather/overview"}})]})
    return {"title": "Alerts", "path": SUBVIEW, "icon": "mdi:bell-ring-outline", "type": "sections",
            "max_columns": 2, "subview": True, "back_path": BACK, "sections": sections}


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
