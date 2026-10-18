"""`automations/kitchen_co2_status_led.yaml`.

The automation keeps its thresholds in two places that must agree: the
`numeric_state` triggers decide WHEN it runs, the `level` template decides
WHAT colour it picks. Move a threshold in one and not the other and nothing
errors — the strip just changes colour at the old value, or not at all until
the next unrelated crossing.
"""
from __future__ import annotations

import pytest
import yaml

from conftest import ROOT

jinja2 = pytest.importorskip("jinja2")

PATH = ROOT / "automations" / "kitchen_co2_status_led.yaml"
AUTOMATION = yaml.safe_load(PATH.read_text())
VARIABLES = next(step["variables"] for step in AUTOMATION["actions"] if "variables" in step)

# The spec: under 600 off, 600-800 yellow, 800-1300 orange, above 1300 red.
THRESHOLDS = [600, 800, 1300]


def _level(ppm: float, trigger_id: str) -> int:
    """Render the automation's own templates, as Home Assistant would."""
    env = jinja2.Environment()
    deadband = int(env.from_string(VARIABLES["deadband"]).render(
        trigger={"id": trigger_id},
    ))
    return int(env.from_string(VARIABLES["level"]).render(ppm=ppm, deadband=deadband))


def _deadband() -> int:
    return int(jinja2.Environment().from_string(VARIABLES["deadband"]).render(
        trigger={"id": "falling"},
    ))


@pytest.mark.parametrize(("ppm", "expected"), [
    (420, 0), (599, 0), (600, 1), (799, 1), (800, 2),
    (1299, 2), (1300, 3), (2500, 3),
])
def test_rising_and_resync_use_the_plain_thresholds(ppm: float, expected: int) -> None:
    assert _level(ppm, "rising") == expected
    assert _level(ppm, "resync") == expected


def test_falling_only_drops_a_level_below_the_deadband() -> None:
    """At 590 ppm on the way down the strip stays yellow; at 549 it goes off.
    Without this a reading wobbling around 600 toggles the strip every update.
    """
    band = _deadband()
    assert band > 0
    for threshold in THRESHOLDS:
        level_above = THRESHOLDS.index(threshold) + 1
        assert _level(threshold - band, "falling") == level_above
        assert _level(threshold - band - 1, "falling") == level_above - 1


def test_triggers_fire_where_the_template_changes_level() -> None:
    """The seam: every level boundary needs a trigger at exactly that value,
    in each direction, or the colour only updates on the next crossing.
    """
    band = _deadband()
    triggers = [t for t in AUTOMATION["triggers"] if t["trigger"] == "numeric_state"]
    rising = sorted(t["above"] for t in triggers if t.get("id") == "rising")
    falling = sorted(t["below"] for t in triggers if t.get("id") == "falling")
    assert rising == THRESHOLDS
    assert falling == [t - band for t in THRESHOLDS]


def test_every_level_has_a_colour() -> None:
    assert len(VARIABLES["colours"]) == len(THRESHOLDS) + 1
