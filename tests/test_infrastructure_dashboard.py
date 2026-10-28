"""The Infrastructure dashboard (`dashboards/infrastructure/`).

The sync checks the entities against HA; what's left to guard here is the
build itself: plain JSON, every Gotthard entity on the page, and templates
that parse, since a broken one only shows as an error card.
"""
from __future__ import annotations

import importlib.util
import json
import re

import pytest

from conftest import ROOT

HERE = ROOT / "dashboards" / "infrastructure"
spec = importlib.util.spec_from_file_location("infrastructure_build", HERE / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
CONFIG = build.build()
USED = set(re.findall(r"\b(?:sensor|binary_sensor|camera|update)\.[a-z0-9_]+", json.dumps(CONFIG)))


def test_build_is_plain_json() -> None:
    assert json.loads(json.dumps(CONFIG)) == CONFIG


def test_every_gotthard_entity_is_shown() -> None:
    """An entity of the integration that the page leaves out is one nobody sees."""
    assert set(build.ENTITIES) <= USED, sorted(set(build.ENTITIES) - USED)


def test_only_the_gotthard_entities() -> None:
    assert USED <= set(build.ENTITIES), sorted(USED - set(build.ENTITIES))


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
