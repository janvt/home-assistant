"""Denise's dashboard (`dashboards/denise/`).

It borrows entities from the Weather and Infrastructure builders and pills
from `pills.py`, so the failures here are drift: a pill key that no longer
exists (its chip silently never shows), a pill without its German words, a
room control slipping in. Its sentences are templates, and a template that
breaks shows an error where Denise expects a sentence, so the important ones
are rendered here on the shapes HA gives them.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re

import pytest

from conftest import ROOT

HERE = ROOT / "dashboards" / "denise"
spec = importlib.util.spec_from_file_location("denise_build", HERE / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
CONFIG = build.build()
TEXT = json.dumps(CONFIG, ensure_ascii=False)
ZURICH = dt.timezone(dt.timedelta(hours=1))


def _templates(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _templates(v)
    elif isinstance(node, list):
        for v in node:
            yield from _templates(v)
    elif isinstance(node, str) and ("{{" in node or "{%" in node):
        yield node


def test_build_is_plain_json() -> None:
    assert json.loads(TEXT) == CONFIG


def test_every_pill_key_exists() -> None:
    """A renamed or removed pill would leave a chip that never turns on."""
    known = {p["key"] for p in build.alerts.ALERTS}
    assert build.PILLS <= known, sorted(build.PILLS - known)
    assert len(build.pills()) == len(build.DE)


def test_every_pill_has_a_chip_and_a_card() -> None:
    for p in build.pills():
        assert TEXT.count(f'"entity": "{build.alerts.entity(p)}"') >= 3, p["key"]  # chip, card, all-quiet


def test_no_room_controls() -> None:
    """Denise doesn't live here: nothing on her page switches anything."""
    controls = r"\b(?:light|switch|climate|cover|fan|lock|media_player|vacuum|input_boolean|script|scene|button)\.[a-z0-9_]+"
    assert not re.findall(controls, TEXT)
    assert "toggle_dismiss" not in TEXT and "perform-action" not in TEXT and "more-info" not in TEXT


def test_axenstrasse_status_traffic_and_closures() -> None:
    for e in (build.AXEN, build.AXEN_NEXT, build.AXEN_CALENDAR, build.TO_ALTDORF, build.TO_BRUNNEN, *build.SPEEDS):
        assert e in TEXT, e
    assert build.AXEN == "binary_sensor.national_roads_axenstrasse" and build.AXEN_CALENDAR in build.roads.CALENDARS


def test_foehn_index_and_outlook() -> None:
    for e in ("sensor.altdorf_fohn", "sensor.altdorf_ur_fohn_outlook", build.GUSTS):
        assert e in TEXT, e


def test_navigation_stays_on_her_own_pages() -> None:
    own = {f"/{build.DASHBOARD}/{v['path']}" for v in CONFIG["views"]}
    paths = set(re.findall(r'"navigation_path": "([^"]+)"', TEXT))
    assert paths <= own, paths - own
    assert CONFIG["views"][1]["back_path"] in own


def test_full_screen_and_a_way_back() -> None:
    """With the header hidden, the Hinweise page's only way back is its own
    back chip."""
    assert CONFIG["kiosk_mode"] == {"hide_header": True, "hide_sidebar": True}
    first = CONFIG["views"][1]["sections"][0]["cards"][0]
    assert first["type"] == "custom:mushroom-chips-card" and first["chips"][0]["type"] == "back"


def test_no_english_left_on_her_page() -> None:
    """She reads German: the English words the borrowed cards used are gone."""
    for word in ("Alerts", "Weather", "Gusts", "Closed", "Next closure", "Open", "All quiet", "Traffic", "Föhn index"):
        assert word not in TEXT, word


# ── rendering, with the handful of HA's template functions they use ─────────
jinja2 = pytest.importorskip("jinja2")


def _env(states: dict[str, str], attrs: dict[str, dict], now: dt.datetime) -> "jinja2.Environment":
    env = jinja2.Environment(undefined=jinja2.StrictUndefined, extensions=["jinja2.ext.loopcontrols"])

    def to_float(v, default=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def as_datetime(v):
        d = dt.datetime.fromisoformat(str(v))
        return d if d.tzinfo else d.replace(tzinfo=ZURICH)

    def is_number(v):
        try:
            float(v)
            return True
        except (TypeError, ValueError):
            return False

    def as_timestamp(v):
        return as_datetime(v).timestamp()

    env.globals.update(
        states=lambda e: states.get(e, "unknown"), is_state=lambda e, s: states.get(e) == s,
        state_attr=lambda e, a: attrs.get(e, {}).get(a), now=lambda: now, as_timestamp=as_timestamp, none=None)
    env.filters.update(
        float=to_float, as_datetime=as_datetime, as_local=lambda d: d.astimezone(ZURICH), is_number=is_number,
        regex_findall=lambda v, p: re.findall(p, v),
        timestamp_custom=lambda ts, fmt: dt.datetime.fromtimestamp(ts, ZURICH).strftime(fmt),
        round=lambda v, n=0: round(float(v), n))
    env.tests["is_number"] = is_number
    return env


NOW = dt.datetime(2026, 11, 7, 19, 30, tzinfo=ZURICH)
STATES = {build.W: "cloudy", build.TEMP_LOW: "4.0", build.TEMP_HIGH: "10.7", build.RAIN_TODAY: "1.0",
          build.AXEN: "on", build.AXEN_CALENDAR: "off", build.FOEHN: "none", build.FOEHN_OUTLOOK: "none",
          build.GUSTS: "18.0", build.TO_ALTDORF: "288.0", build.TO_BRUNNEN: "504.0",
          build.SPEEDS[0]: "49.15", build.SPEEDS[1]: "46.8"}
ATTRS = {build.W: {"temperature": 10.6}, build.AXEN: {"closures": []},
         build.AXEN_NEXT: {"closures": [{
             "text": "Freigegeben: A4 Altdorf <-> Brunnen Tunnel Flüelen-Tunnel Sachlage: Tunnel gesperrt Baustelle "
                     "Dauer: nachts voraussichtlich 09.11.2026 22:00 bis 10.11.2026 05:00 Empfehlung: eine lokale "
                     "Umleitung ist eingerichtet",
             "start": "2026-11-09T21:00:00+00:00", "end": "2026-11-10T05:00:00+01:00", "direction": "both"}]}}


def render(template: str, **overrides: str) -> str:
    return _env({**STATES, **overrides}, ATTRS, NOW).from_string(template).render()


def test_every_template_parses() -> None:
    env = jinja2.Environment(extensions=["jinja2.ext.loopcontrols"])
    for t in _templates(CONFIG):
        env.parse(t)


def test_greeting_reads_as_sentences() -> None:
    out = render(build.GREETING)
    assert "Guten Abend, Denise" in out
    assert "Bewölkt, 11 °C in Altdorf. Heute 4 bis 11 °C, 1.0 mm Regen." in out
    assert "Die Axenstrasse ist **offen**." in out
    assert "**gesperrt**" in render(build.GREETING, **{build.AXEN: "off"})


def test_closures_list_their_days_and_what_is_closed() -> None:
    """A night closure crosses midnight: the end gets its own weekday."""
    out = render(build.AXEN_CLOSURES)
    assert "- Mo 09.11., 22:00 bis Di 05:00 Uhr<br><small>Tunnel gesperrt Baustelle</small>" in out
    ATTRS[build.AXEN_NEXT]["closures"], saved = [], ATTRS[build.AXEN_NEXT]["closures"]
    try:
        assert "Keine Sperrungen angekündigt." in render(build.AXEN_CLOSURES)
    finally:
        ATTRS[build.AXEN_NEXT]["closures"] = saved


def test_axenstrasse_status_and_traffic() -> None:
    assert 'title="Offen"' in render(build.AXEN_STATUS)
    ATTRS[build.AXEN_CALENDAR] = {"end_time": "2026-11-10 05:00:00"}  # the calendar's local, naive times
    try:
        closed = render(build.AXEN_STATUS, **{build.AXEN: "off", build.AXEN_CALENDAR: "on"})
    finally:
        del ATTRS[build.AXEN_CALENDAR]
    assert 'title="Gesperrt"' in closed and "Voraussichtlich bis 05:00 Uhr." in closed
    assert "zurzeit gesperrt" in render(build.AXEN_STATUS, **{build.AXEN: "off"})
    out = render(build.AXEN_TRAFFIC)
    assert "läuft flüssig" in out and "Rund 290 Fahrzeuge pro Stunde Richtung Altdorf, 500 Richtung Brunnen." in out
    assert "Stau" in render(build.AXEN_TRAFFIC, **{build.SPEEDS[0]: "12"})
    assert render(build.AXEN_TRAFFIC, **{build.TO_ALTDORF: "unavailable"}) == ""


@pytest.mark.parametrize(("foehn", "outlook", "title"), [
    ("foehn", "none", "Der Föhn bläst"), ("mixed", "none", "Ein wenig Föhn"),
    ("none", "strong_south", "Starker Föhn im Anzug"), ("none", "south", "Föhn im Anzug"),
    ("none", "none", "Kein Föhn"), ("none", "north", "Kein Föhn")])
def test_foehn_in_one_sentence(foehn: str, outlook: str, title: str) -> None:
    out = render(build.FOEHN_TEXT, **{build.FOEHN: foehn, build.FOEHN_OUTLOOK: outlook})
    assert f'title="{title}"' in out
