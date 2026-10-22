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
    prefixes = (f"{build.CAMERA}_", f"{build.ZONE}_", "frigate_")
    assert all(e.split(".", 1)[1].startswith(prefixes) or e == f"camera.{build.CAMERA}" for e in USED), sorted(USED)
