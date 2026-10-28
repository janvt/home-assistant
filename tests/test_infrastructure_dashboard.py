"""The Infrastructure dashboard (`dashboards/infrastructure/`).

The sync checks the entities against HA; what's left to guard here is the
build itself: plain JSON, every Gotthard and pass entity on the page, and
templates that parse, since a broken one only shows as an error card.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import re
import sys

import pytest

from conftest import ROOT

HERE = ROOT / "dashboards" / "infrastructure"
spec = importlib.util.spec_from_file_location("infrastructure_build", HERE / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
CONFIG = build.build()
USED = set(re.findall(r"\b(?:sensor|binary_sensor|camera|update|calendar)\.[a-z0-9_]+", json.dumps(CONFIG)))


def test_build_is_plain_json() -> None:
    assert json.loads(json.dumps(CONFIG)) == CONFIG


def test_every_gotthard_entity_is_shown() -> None:
    """An entity of the integration that the page leaves out is one nobody sees."""
    assert set(build.ENTITIES) <= USED, sorted(set(build.ENTITIES) - USED)


def test_every_pass_entity_is_shown() -> None:
    """The same for the Alpine Passes integration: seven entities per pass."""
    assert len(build.PASS_ENTITIES) == 7 * len(build.PASSES)
    assert set(build.PASS_ENTITIES) <= USED, sorted(set(build.PASS_ENTITIES) - USED)


def test_only_the_gotthard_and_pass_entities() -> None:
    known = set(build.ENTITIES) | set(build.PASS_ENTITIES)
    assert USED <= known, sorted(USED - known)


def _sync():
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent))
    try:
        spec = importlib.util.spec_from_file_location("infrastructure_sync", HERE / "sync.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(HERE))
        sys.path.remove(str(HERE.parent))


def test_sync_sees_a_view_it_would_drop() -> None:
    """A view HA has that build.py doesn't make is gone after a save: the
    Passes view was, once, when it was synced from another branch."""
    websockets = pytest.importorskip("websockets")  # noqa: F841 ha_client needs it
    sync = _sync()
    old = {"views": [*CONFIG["views"], {"title": "Mine", "path": "mine", "cards": []}]}
    assert sync.dropped_views(old, CONFIG) == ["mine"]
    assert sync.dropped_views(CONFIG, CONFIG) == []


def test_templates_parse() -> None:
    """Every markdown card, on both views."""
    jinja2 = pytest.importorskip("jinja2")
    cards = [card for view in CONFIG["views"] for section in view["sections"] for card in section["cards"]]
    templates = [card["content"] for card in cards if card["type"] == "markdown"]
    assert len(templates) >= 8
    for template in templates:
        jinja2.Environment().parse(template)


def test_closure_lists_render_both_kinds_of_closure() -> None:
    """A road's closures have a start and an end, the open/closed sensor's an
    "until": the list must show both, and "now" for a closure without a start.
    Strict, as HA renders it: reading a key a closure lacks is an error there."""
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    env.filters["regex_replace"] = lambda value, find, replace: re.sub(find, replace, value)
    env.filters["timestamp_custom"] = lambda value, fmt: f"<{value}>"
    env.globals["as_timestamp"] = lambda value: value
    closures = {"closures": [{"text": "Freigegeben: A4 Altdorf <-> Brunnen Sachlage: Strecke gesperrt",
                              "until": "T1"}],
                "planned": [{"text": "Freigegeben: A2 x", "start": "T0", "end": "T1"}]}
    env.globals["state_attr"] = lambda entity, attribute: closures.get(attribute)
    now = env.from_string(build.closure_list("x", "closures", "Open.")).render()
    assert now == "- **now to <T1>**: A4 Altdorf <-> Brunnen Sachlage: Strecke gesperrt\n"
    planned = env.from_string(build.closure_list("x", "planned", "None.")).render()
    assert planned == "- **<T0> to <T1>**: A2 x\n"
    assert env.from_string(build.closure_list("x", "current", "Open.")).render() == "Open."


def test_message_prefix_is_stripped() -> None:
    """The regex reaches HA's regex_replace as `^\\w+: `: one backslash too few
    and every message keeps its "Freigegeben:"."""
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment()
    env.filters["regex_replace"] = lambda value, find, replace: re.sub(find, replace, value)
    env.globals["state_attr"] = lambda entity, attribute: [
        {"text": "Freigegeben: A2 Luzern -> Gotthard Sachlage: Stau", "end": None}]
    rendered = env.from_string(build.MESSAGE_LIST).render()
    assert rendered == "- A2 Luzern -> Gotthard Sachlage: Stau\n"


def strict_env(states: dict[str, str], attributes: dict[tuple[str, str], object]):
    """Jinja as HA renders a markdown card: strict, with stand-ins for HA's
    functions, reading the given states and attributes."""
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    env.filters["timestamp_custom"] = lambda value, fmt: f"<{value}>"
    env.globals["as_timestamp"] = lambda value, default: default if value in ("unknown", "unavailable") else value
    env.globals["states"] = lambda entity: states.get(entity, "unknown")
    env.globals["is_state"] = lambda entity, state: states.get(entity) == state
    env.globals["is_number"] = lambda value: value.lstrip("-").replace(".", "", 1).isdigit()
    env.globals["state_attr"] = lambda entity, attribute: attributes.get((entity, attribute))
    env.globals["state_translated"] = lambda entity: {"open": "Open"}.get(states.get(entity), "Unknown")
    env.globals["now"] = lambda: datetime.datetime(2026, 10, 28, 15, 0)
    return env


def test_conditions_table_renders_a_row_per_pass() -> None:
    """With the site's words, the flags, and dashes for what isn't known (a
    pass the integration lost, say): strict, as in HA."""
    env = strict_env({"sensor.gotthardpass_status_since": "T0", "sensor.gotthardpass_temperature": "-0.4",
                      "sensor.gotthardpass_weather": "snow",
                      "binary_sensor.gotthardpass_snow_chains_required": "on"},
                     {("sensor.gotthardpass_status", "status"): "Open, with restrictions"})
    rows = env.from_string(build.conditions_table()).render().splitlines()
    assert len(rows) == 2 + len(build.PASSES)
    assert "| Gotthardpass | Open, with restrictions · snow chains | <T0> | 0 | snow |" in rows
    assert "| Furkapass | unknown | – | – | – |" in rows


def test_notices_list_pass_by_pass() -> None:
    """A pass's notices are one per line: a list item each, under the pass
    and its route; passes without notices are left out."""
    env = strict_env({}, {("sensor.gotthardpass_status", "notes"): "Nachtsperre.\nTremola: 3.5 t.",
                          ("sensor.gotthardpass_status", "route"): "Hospental - Airolo",
                          ("sensor.furkapass_status", "notes"): "Wintersperre."})
    assert env.from_string(build.notices_list()).render() == (
        "**Gotthardpass**, Hospental - Airolo\n- Nachtsperre.\n- Tremola: 3.5 t.\n\n"
        "**Furkapass**\n- Wintersperre.\n\n")
    assert strict_env({}, {}).from_string(build.notices_list()).render() == "No notices."


def pass_cards() -> list[dict]:
    view = next(v for v in CONFIG["views"] if v["path"] == "passes")
    return [card for section in view["sections"] for card in section["cards"]
            if card["type"] == "custom:mushroom-template-card"]


def test_a_card_per_pass() -> None:
    assert [card["entity"] for card in pass_cards()] == [f"sensor.{slug}_status" for slug in build.PASSES]


def render_card(states: dict[str, str]) -> dict[str, str]:
    """The Klausen card's templates, rendered strictly as HA does."""
    env = strict_env(states, {})
    env.filters["timestamp_custom"] = lambda value, fmt: {"%H:%M": "08:30", "%d.%m.": "26.10.",
                                                          "%Y-%m-%d": value}[fmt]
    card = pass_cards()[0]
    return {key: env.from_string(card[key]).render()
            for key in ("icon", "color", "secondary", "badge_icon")}


def test_pass_card_by_status() -> None:
    """Icon and color follow the status; the second line has it in words, the
    temperature, and the date it changed (not today)."""
    card = render_card({"sensor.klausenpass_status": "open", "sensor.klausenpass_temperature": "-0.4",
                        "sensor.klausenpass_status_since": "2026-10-26"})
    assert card == {"icon": "mdi:check-circle", "color": "green",
                    "secondary": "Open · 0 °C · since 26.10.", "badge_icon": ""}


def test_pass_card_changed_today_and_chains() -> None:
    card = render_card({"sensor.klausenpass_status": "restricted", "sensor.klausenpass_status_since": "2026-10-28",
                        "binary_sensor.klausenpass_snow_chains_required": "on"})
    assert card["icon"] == "mdi:snowflake" and card["color"] == "amber"
    assert card["secondary"].endswith(" · since 08:30")
    assert card["badge_icon"] == "mdi:link-variant"


def test_pass_card_unknown() -> None:
    """The integration lost the pass, or HA just started: grey, a question mark."""
    card = render_card({})
    assert card == {"icon": "mdi:help-circle", "color": "grey", "secondary": "Unknown", "badge_icon": ""}


def test_every_status_has_a_look() -> None:
    assert set(build.PASS_LOOK) == {"open", "restricted", "partially_open", "closed", "winter_closure"}
