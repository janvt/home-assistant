"""The road closure notice blueprint (`blueprints/automation/janvt/`).

A blueprint that loads can still go quiet: an input nothing reads, a key a
closure lacks (HA's templates are strict, so the template errors and nothing
is sent), or a restart taken for "open again". The templates run here under
StrictUndefined against the attribute shapes the Gotthard integration makes.
"""
from __future__ import annotations

import datetime
import re
from types import SimpleNamespace

import pytest

from conftest import ROOT

yaml = pytest.importorskip("yaml")
jinja2 = pytest.importorskip("jinja2")

PATH = ROOT / "blueprints" / "automation" / "janvt" / "road_closure_notice.yaml"


class Input(str):
    """An `!input name`, kept as itself."""


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!input", lambda loader, node: Input(loader.construct_scalar(node)))
BLUEPRINT = yaml.load(PATH.read_text(), Loader=Loader)
TEXT = PATH.read_text()

AXEN = "binary_sensor.national_roads_axenstrasse"
A4_NORTH = "sensor.national_roads_a4_closures_northbound_to_schaffhausen"
A4_SOUTH = "sensor.national_roads_a4_closures_southbound_to_altdorf"
NEXT_AXEN = "sensor.national_roads_next_axenstrasse_closure"
CLOSURE = "Freigegeben: A4 Altdorf <-> Brunnen zwischen Ortschaft Flüelen und Ortschaft Sisikon Sachlage: Strecke gesperrt"


def inputs_used(node) -> set[str]:
    if isinstance(node, Input):
        return {str(node)}
    if isinstance(node, dict):
        return set().union(*map(inputs_used, node.values())) if node else set()
    if isinstance(node, list):
        return set().union(*map(inputs_used, node)) if node else set()
    return set()


def test_every_input_is_used_and_declared() -> None:
    declared = set(BLUEPRINT["blueprint"]["input"])
    used = inputs_used({k: v for k, v in BLUEPRINT.items() if k != "blueprint"})
    assert used == declared, (sorted(declared - used), sorted(used - declared))


def test_source_url_is_this_file() -> None:
    """HA re-imports a blueprint from its source_url: a wrong one updates
    nothing, or something else."""
    url = BLUEPRINT["blueprint"]["source_url"]
    assert url.endswith("/" + PATH.relative_to(ROOT).as_posix()), url


def test_templates_parse() -> None:
    env = jinja2.Environment()
    templates = re.findall(r"\{[{%].*?[}%]\}", TEXT, re.S)
    assert templates
    for block in _strings(BLUEPRINT):
        if "{{" in block or "{%" in block:
            env.parse(block)


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)


# ── the templates, as HA runs them ──────────────────────────────────────────
NOW = datetime.datetime(2026, 11, 2, 7, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=1)))  # a Monday


def state(entity_id: str, value: str, **attributes) -> SimpleNamespace:
    return SimpleNamespace(entity_id=entity_id, state=value, attributes=attributes,
                           name=attributes.get("friendly_name", entity_id), domain=entity_id.split(".")[0])


def env(states: dict[str, SimpleNamespace]) -> jinja2.Environment:
    e = jinja2.Environment(undefined=jinja2.StrictUndefined)
    e.filters["regex_replace"] = lambda value, find, replace: re.sub(find, replace, value)
    e.filters["slugify"] = lambda value: re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    e.filters["timestamp_custom"] = lambda value, fmt: datetime.datetime.fromtimestamp(value, NOW.tzinfo).strftime(fmt)
    e.globals["as_timestamp"] = lambda value: (datetime.datetime.fromisoformat(value) if isinstance(value, str)
                                               else value).timestamp()
    e.globals["now"] = lambda: NOW
    e.globals["state_attr"] = lambda entity, attribute: states[entity].attributes.get(attribute) if entity in states else None
    return e


def variables(**overrides):
    defaults = {"roads": [AXEN, A4_NORTH, A4_SOUTH, NEXT_AXEN], "reopened": True,
                "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "after": "00:00:00", "before": "00:00:00", "reminder": False}
    return {**defaults, **overrides}


CONDITION = BLUEPRINT["conditions"][0]["value_template"]
CHANGE = BLUEPRINT["actions"][0]["choose"][0]["sequence"]
FRESH = CHANGE[0]["variables"]["fresh"]
KEY = CHANGE[0]["variables"]["key"]


def condition(trigger, states=None, **overrides) -> bool:
    out = env(states or {}).from_string(CONDITION).render(trigger=trigger, **variables(**overrides))
    return out.strip() == "True"


def fresh(trigger, states) -> list:
    e = env(states)
    v = variables()
    key = e.from_string(KEY).render(trigger=trigger, **v)
    import ast
    return ast.literal_eval(e.from_string(FRESH).render(trigger=trigger, key=key, **v).strip())


def change(entity_id, old, new):
    return SimpleNamespace(id="change", entity_id=entity_id, from_state=old, to_state=new)


def test_a_restart_sends_nothing() -> None:
    """Unavailable → on is HA starting, not the road opening again."""
    trigger = change(AXEN, state(AXEN, "unavailable"), state(AXEN, "on", closures=[]))
    assert not condition(trigger)
    assert not condition(change(AXEN, None, state(AXEN, "on", closures=[])))


def test_only_on_the_days_and_hours_chosen() -> None:
    trigger = change(AXEN, state(AXEN, "on", closures=[]), state(AXEN, "off", closures=[{"text": CLOSURE}]))
    assert condition(trigger)
    assert not condition(trigger, days=["sat", "sun"])
    assert condition(trigger, after="06:00:00", before="09:00:00")
    assert not condition(trigger, after="16:00:00", before="19:00:00")
    # A window past midnight.
    assert condition(trigger, after="22:00:00", before="08:00:00")


def test_a_new_closure_is_sent_once() -> None:
    """The Axenstrasse's closure is on the A4 too, both ways: only the first
    road in the list sends it."""
    closures = [{"text": CLOSURE, "until": "2026-11-03T05:00:00+01:00", "direction": "both"}]
    current = [{"text": CLOSURE, "start": None, "end": "2026-11-03T05:00:00+01:00", "direction": "both"}]
    states = {AXEN: state(AXEN, "off", closures=closures), A4_NORTH: state(A4_NORTH, "1", current=current, planned=[]),
              A4_SOUTH: state(A4_SOUTH, "1", current=current, planned=[]), NEXT_AXEN: state(NEXT_AXEN, "unknown", closures=[])}
    axen = change(AXEN, state(AXEN, "on", closures=[]), states[AXEN])
    assert [c["text"] for c in fresh(axen, states)] == [CLOSURE]
    a4 = change(A4_NORTH, state(A4_NORTH, "0", current=[], planned=[]), states[A4_NORTH])
    assert fresh(a4, states) == []


def test_only_closures_that_are_new() -> None:
    """A second closure while the road is already closed: that one only."""
    other = CLOSURE.replace("Flüelen und Ortschaft Sisikon", "Sisikon und Kreuzung Abzweigung Morschach")
    old = state(AXEN, "off", closures=[{"text": CLOSURE, "until": None, "direction": "both"}])
    new = state(AXEN, "off", closures=[{"text": CLOSURE, "until": None, "direction": "both"},
                                       {"text": other, "until": None, "direction": "both"}])
    assert [c["text"] for c in fresh(change(AXEN, old, new), {AXEN: new})] == [other]


def test_notice_message_renders_both_shapes() -> None:
    """An open/closed sensor's closure has "until", a road's "end": the
    message must take either, or none."""
    message = CHANGE[1]["repeat"]["sequence"][0]["message"]
    e = env({})
    for item in ({"text": CLOSURE, "until": "2026-11-03T05:00:00+01:00"}, {"text": CLOSURE, "end": None, "start": None},
                 {"text": CLOSURE}):
        out = e.from_string(message).render(repeat=SimpleNamespace(item=item)).strip()
        assert out.startswith("A4 Altdorf <-> Brunnen"), out
    assert out.endswith("Strecke gesperrt")


def test_evening_reminder_lists_the_next_24_hours_once() -> None:
    reminder = BLUEPRINT["actions"][0]["choose"][1]["sequence"]
    soon = reminder[0]["variables"]["soon"]
    tonight = {"text": CLOSURE, "start": "2026-11-02T22:00:00+01:00", "end": "2026-11-03T05:00:00+01:00", "direction": "both"}
    later = dict(tonight, text=CLOSURE + " x", start="2026-11-09T22:00:00+01:00")
    states = {NEXT_AXEN: state(NEXT_AXEN, "x", closures=[tonight, later]),
              A4_NORTH: state(A4_NORTH, "0", current=[], planned=[tonight]), AXEN: state(AXEN, "on", closures=[])}
    import ast
    out = ast.literal_eval(env(states).from_string(soon).render(**variables(roads=[AXEN, NEXT_AXEN, A4_NORTH])).strip())
    assert [c["text"] for c in out] == [CLOSURE]
    message = reminder[1]["then"][0]["message"]
    assert "22:00–05:00: A4 Altdorf" in env(states).from_string(message).render(soon=out)
