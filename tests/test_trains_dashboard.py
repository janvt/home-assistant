"""The Trains debug dashboard (`dashboards/trains/`).

The sync checks the entities against HA; what's left to guard here is the
build itself: plain JSON, and every Frigate diagnostic it shows either on by
default or in the list the sync enables, or the tile reads "unavailable".
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys

import pytest

from conftest import ROOT

HERE = ROOT / "dashboards" / "trains"


def _load(name: str):
    sys.path.insert(0, str(HERE))
    try:
        spec = importlib.util.spec_from_file_location(f"trains_{name}", HERE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(HERE))


build = _load("build")
CONFIG = build.build()
USED = set(re.findall(r"\b(?:sensor|binary_sensor|camera|image|switch|number|update)\.[a-z0-9_]+",
                      json.dumps(CONFIG)))


def test_build_is_plain_json() -> None:
    assert json.loads(json.dumps(CONFIG)) == CONFIG


def test_every_enabled_diagnostic_is_shown() -> None:
    """Enabling an entity nobody looks at only fills the recorder."""
    assert set(build.DISABLED_BY_DEFAULT) <= USED, sorted(set(build.DISABLED_BY_DEFAULT) - USED)


def test_only_frigate_entities() -> None:
    """Frigate's own entities, plus the train count the pills' sync makes."""
    prefixes = (f"{build.CAMERA}_", f"{build.WIDE}_", f"{build.TELE}_", f"{build.ZONE}_", "frigate_")
    others = {f"camera.{c}" for c in (build.CAMERA, build.WIDE, build.TELE)} | {
        build.PASSING, build.TODAY, build.THIS_HOUR, build.TELE_PASSING, build.TELE_TODAY, build.TELE_THIS_HOUR}
    assert all(e.split(".", 1)[1].startswith(prefixes) or e in others for e in USED), sorted(USED)


# ── the timetable matching ──────────────────────────────────────────────────
timetable = _load("timetable")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def test_timetable_sensors_are_the_ones_the_matching_reads() -> None:
    """The REST sensors' entity ids come from their names in the pasted YAML;
    rename one there and the matching reads an attribute that's never set, so
    every train comes out as "no timetable train"."""
    yaml = pytest.importorskip("yaml")
    rest = yaml.safe_load((HERE / "ha-timetable.yaml").read_text())["rest"]
    names = [f"sensor.{_slug(s['name'])}" for block in rest for s in block["sensor"]]
    assert names == timetable.BOARDS
    assert all(block["scan_interval"] >= 300 for block in rest), "a free community API: don't poll faster"


def test_helper_names_give_the_entity_ids_the_automation_writes() -> None:
    """input_number/input_text helpers get their id from the name; a mismatch
    means the sync creates one helper and the automation writes another."""
    for helper in timetable.NUMBERS + timetable.TEXTS:
        assert helper["entity"].split(".", 1)[1] == _slug(helper["name"]), helper["name"]


def test_timetable_templates_parse() -> None:
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment()
    env.filters.setdefault("int", lambda value, *args: value)
    env.parse(timetable.MATCH)
    yaml = pytest.importorskip("yaml")
    for block in yaml.safe_load((HERE / "ha-timetable.yaml").read_text())["rest"]:
        env.parse(block["resource_template"])


def test_the_automation_handles_every_camera() -> None:
    auto = timetable.automation()
    assert {t["id"] for t in auto["triggers"]} == set(timetable.CAMERAS)
    branches = auto["actions"][0]["choose"]
    assert [b["sequence"][0]["target"]["entity_id"] for b in branches] == [t for _, t in timetable.CAMERAS.values()]
