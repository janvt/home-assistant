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
CRITICAL: set[str] = _pills["CRITICAL"]
NUMBERS: list[dict[str, Any]] = _pills.get("NUMBERS", [])
STATISTICS: list[dict[str, Any]] = _pills.get("STATISTICS", [])
TEMPLATES: list[dict[str, Any]] = _pills.get("TEMPLATES", [])
HISTORY_STATS: list[dict[str, Any]] = _pills.get("HISTORY_STATS", [])

DASHBOARD = "dashboard-mobile"
SUBVIEW = "weather-alerts"
COUNT = "sensor.weather_alerts_active"
# Icons that fit one phone-width row (36 px chips, 8 px apart).
PLACES = 6
NAV = {"action": "navigate", "navigation_path": f"/{DASHBOARD}/{SUBVIEW}"}
GROUP_ICONS = {
    "Safety": "mdi:shield-home-outline", "Kitchen": "mdi:fridge-outline",
    "Travel": "mdi:train", "Rivers": "mdi:waves", "Forecast": "mdi:crystal-ball", "Weather now": "mdi:weather-partly-cloudy",
    "Mountains": "mdi:image-filter-hdr", "Home": "mdi:home-outline",
    "Calendar": "mdi:calendar-star", "Climate": "mdi:chart-bell-curve", "Proxmox": "mdi:server", "Maintenance": "mdi:wrench-outline",
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


def dismissed_entity(pill: dict[str, Any]) -> str:
    return f"input_datetime.pill_{pill['key']}_dismissed"


def dismissable(pill: dict[str, Any]) -> bool:
    return pill["key"] not in CRITICAL


# A pill is shown when it's on and turned on after its last dismissal. Critical
# pills have no dismiss helper, so state_attr() gives 0 and they always show.
# Dismissed pills come back by themselves the next time they turn on.
SHOWN = ("is_state(b, 'on') and state_attr('input_datetime.' ~ b[14:] ~ '_dismissed', 'timestamp')|float(0)"
         " < as_timestamp(states[b].last_changed)")
COUNT_TEMPLATE = ("{% set ns = namespace(n=0) %}{% for s in states.binary_sensor"
                  " | selectattr('entity_id','match','binary_sensor\\\\.pill_') %}{% set b = s.entity_id %}"
                  "{% if " + SHOWN + " %}{% set ns.n = ns.n + 1 %}{% endif %}{% endfor %}{{ ns.n }}")
TOGGLE_SCRIPT = "pill_toggle_dismiss"
SCRIPT = {
    "alias": "Pill: dismiss or bring back",
    "description": "Hides an alert pill until it turns off and on again, or brings a dismissed one back. "
                   "Managed by dashboards/mobile-alerts/sync.py.",
    "mode": "queued",
    "fields": {"key": {"name": "Pill", "description": "The pill's key, e.g. fohn_altdorf", "required": True,
                       "selector": {"text": {}}}},
    "sequence": [
        {"variables": {"b": "binary_sensor.pill_{{ key }}", "d": "input_datetime.pill_{{ key }}_dismissed"}},
        {"condition": "template", "value_template": "{{ states(d) not in ['unknown', 'unavailable'] }}"},
        {"action": "input_datetime.set_datetime", "target": {"entity_id": "{{ d }}"},
         "data": {"timestamp": "{{ 0 if state_attr(d, 'timestamp')|float(0) >= as_timestamp(states[b].last_changed)"
                               " else now().timestamp() }}"}},
    ],
}


def is_dismissed(pill: dict[str, Any]) -> str:
    """Template test: the pill is on but dismissed."""
    return ("state_attr('" + dismissed_entity(pill) + "','timestamp')|float(0) >= "
            "as_timestamp(states." + entity(pill) + ".last_changed)")


_ACTIVE = (
    "{% set ns = namespace(a=[]) %}{% for k in "
    + json.dumps([p["key"] for p in ALERTS])
    + " %}{% set b = 'binary_sensor.pill_' ~ k %}{% if " + SHOWN + " %}"
    "{% set ns.a = ns.a + [k] %}{% endif %}{% endfor %}"
)


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


def _pick(index: int, field: str) -> str:
    """Template for the icon, colour or content of the index-th active pill."""
    table = json.dumps({p["key"]: p.get(field, "") for p in ALERTS if field != "content"})
    head = (_ACTIVE + "{% set m = " + table + " %}"
            "{% set k = ns.a[" + str(index) + "] if ns.a|count > " + str(index) + " else '' %}")
    if field == "content":
        dynamic = {p["key"]: p["content"] for p in ALERTS if p.get("content")}
    else:
        dynamic = {p["key"]: color(p) for p in ALERTS if field == "color" and p.get("color_from")}
    if not dynamic:
        return head + "{{ m[k] if k else '' }}"
    branches = "".join(("{% if " if i == 0 else "{% elif ") + f"k == '{key}' %}}" + value
                       for i, (key, value) in enumerate(dynamic.items()))
    return head + branches + "{% else %}{{ m[k] if k else '' }}{% endif %}"


def chips() -> list[dict[str, Any]]:
    states = count_states()

    def place(index: int, shown_for: list[str]) -> dict[str, Any]:
        chip = {"type": "template", "icon": _pick(index, "icon"), "icon_color": _pick(index, "color"),
                "tap_action": NAV}
        if any(p.get("content") for p in ALERTS):
            chip["content"] = _pick(index, "content")
        return {"type": "conditional", "conditions": _cond(shown_for), "chip": chip}

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


BACK = f"/{DASHBOARD}/0"


def back_chips(*extra: dict[str, Any]) -> dict[str, Any]:
    """Mushroom's back chip, the way every other page of this dashboard starts."""
    return {"type": "custom:mushroom-chips-card", "chips": [{"type": "back"}, *extra]}


def subview() -> dict[str, Any]:
    active = [
        back_chips(),
        {"type": "heading", "heading": "Active now", "heading_style": "title", "icon": "mdi:bell-ring-outline"},
        {"type": "markdown", "content": "<small>Hold a card to dismiss it until it clears and comes back; hold "
                                        "again to bring it back. Safety alerts can't be dismissed.</small>"},
        {"type": "markdown", "content": "All quiet: nothing needs your attention right now.",
         "visibility": [{"condition": "state", "entity": COUNT, "state": "0"}]},
    ]
    for p in ALERTS:
        card = {
            "type": "custom:mushroom-template-card", "entity": entity(p),
            "primary": p["name"], "secondary": p["secondary"], "icon": p["icon"], "icon_color": color(p),
            "multiline_secondary": True, "fill_container": True, "grid_options": {"columns": 12},
            "tap_action": {"action": "more-info"},
            "visibility": [{"condition": "state", "entity": entity(p), "state": "on"}],
        }
        if dismissable(p):
            card["secondary"] = ("{% if " + is_dismissed(p) + " %}Dismissed · hold to bring back{% else %}"
                                 + p["secondary"] + "{% endif %}")
            card["icon_color"] = "{% if " + is_dismissed(p) + " %}disabled{% else %}" + color(p) + "{% endif %}"
            card["hold_action"] = {"action": "perform-action", "perform_action": f"script.{TOGGLE_SCRIPT}",
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
