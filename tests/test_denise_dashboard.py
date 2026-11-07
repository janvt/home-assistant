"""Denise's dashboard (`dashboards/denise/`).

It borrows cards from the Weather and Infrastructure builders and pills from
`pills.py`, so the failures here are drift: a pill key that no longer exists
(its chip silently never shows), a room control slipping in, a card naming an
entity of the wrong integration.
"""
from __future__ import annotations

import importlib.util
import json
import re

from conftest import ROOT

HERE = ROOT / "dashboards" / "denise"
spec = importlib.util.spec_from_file_location("denise_build", HERE / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
CONFIG = build.build()
TEXT = json.dumps(CONFIG)


def _cards(node):
    if isinstance(node, dict):
        if "type" in node and ("entity" in node or "entities" in node or "chips" in node):
            yield node
        for v in node.values():
            yield from _cards(v)
    elif isinstance(node, list):
        for v in node:
            yield from _cards(v)


def test_build_is_plain_json() -> None:
    assert json.loads(TEXT) == CONFIG


def test_every_pill_key_exists() -> None:
    """A renamed or removed pill would leave a chip that never turns on."""
    known = {p["key"] for p in build.alerts.ALERTS}
    assert build.PILLS <= known, sorted(build.PILLS - known)


def test_every_pill_has_a_chip_and_a_card() -> None:
    for p in build.pills():
        assert TEXT.count(f'"entity": "{build.alerts.entity(p)}"') >= 3, p["key"]  # chip, card, all-quiet


def test_no_room_controls() -> None:
    """Denise doesn't live here: nothing on her page switches anything."""
    controls = r"\b(?:light|switch|climate|cover|fan|lock|media_player|vacuum|input_boolean|script|scene|button)\.[a-z0-9_]+"
    assert not re.findall(controls, TEXT)
    assert "toggle_dismiss" not in TEXT and "perform-action" not in TEXT


def test_axenstrasse_status_flow_and_calendar() -> None:
    for e in (build.roads.AXENSTRASSE, build.roads.AXEN_TRAFFIC, build.roads.AXEN_CLOSURE, build.AXEN_CALENDAR,
              build.roads.station(build.AXEN_STATION, "south", "traffic"),
              build.roads.station(build.AXEN_STATION, "north", "traffic")):
        assert f'"{e}"' in TEXT, e
    assert build.AXEN_CALENDAR in build.roads.CALENDARS


def test_foehn_index_and_outlook() -> None:
    s = build.weather.slug(build.ALTDORF)
    for e in ("sensor.altdorf_fohn", f"sensor.{s}_fohn_outlook", f"sensor.{s}_fohn_pressure_difference"):
        assert f'"entity": "{e}"' in TEXT, e


def test_navigation_stays_on_known_pages() -> None:
    """Her own Alerts page, and Altdorf on the Weather dashboard."""
    weather_views = {f"{build.weather.BASE}/{v['path']}" for v in build.weather.build()["views"]}
    own = {f"/{build.DASHBOARD}/{v['path']}" for v in CONFIG["views"]}
    paths = set(re.findall(r'"navigation_path": "([^"]+)"', TEXT))
    assert paths <= own | weather_views, paths - own - weather_views
    assert CONFIG["views"][1]["back_path"] in own


def test_full_screen_and_a_way_back() -> None:
    """With the header hidden, the Alerts sub-page's only way back is its own
    back chip."""
    assert CONFIG["kiosk_mode"] == {"hide_header": True, "hide_sidebar": True}
    alerts = CONFIG["views"][1]["sections"][0]["cards"][0]
    assert alerts["type"] == "custom:mushroom-chips-card" and alerts["chips"][0]["type"] == "back"
