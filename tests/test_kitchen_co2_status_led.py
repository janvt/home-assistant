"""`automations/kitchen_co2_status_led.yaml` and `packages/kitchen_co2.yaml`.

The automation keeps its thresholds in two places that must agree: the
`numeric_state` triggers decide WHEN it runs, the `level` template decides
WHAT colour it picks. Move a threshold in one and not the other and nothing
errors — the strip just changes colour at the old value, or not at all until
the next unrelated crossing.

The automation reads a 10-minute mean defined in the package, not the raw
sensor. That entity id is a second seam: rename the statistics sensor and
the automation's numeric_state triggers simply never fire again.
"""
from __future__ import annotations

import pytest
import yaml

from conftest import ROOT

jinja2 = pytest.importorskip("jinja2")

PATH = ROOT / "automations" / "kitchen_co2_status_led.yaml"
AUTOMATION = yaml.safe_load(PATH.read_text())
PACKAGE = yaml.safe_load((ROOT / "packages" / "kitchen_co2.yaml").read_text())
MEAN = "sensor.kitchen_co2_10min_mean"
RAW = "sensor.ultimatesensor_scd41_co2"
VARIABLES = next(step["variables"] for step in AUTOMATION["actions"] if "variables" in step)

# The spec: under 900 off, 900-1200 yellow, 1200-1500 orange, above 1500 red.
THRESHOLDS = [900, 1200, 1500]


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
    (420, 0), (899, 0), (900, 1), (1199, 1), (1200, 2),
    (1499, 2), (1500, 3), (2500, 3),
])
def test_rising_and_resync_use_the_plain_thresholds(ppm: float, expected: int) -> None:
    assert _level(ppm, "rising") == expected
    assert _level(ppm, "resync") == expected


def test_falling_only_drops_a_level_below_the_deadband() -> None:
    """At 850 ppm on the way down the strip stays yellow; at 849 it goes off.
    Without this a reading wobbling around 900 toggles the strip every update.
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


def _statistics_sensor() -> dict:
    sensors = [s for s in PACKAGE["sensor"] if s.get("platform") == "statistics"]
    assert len(sensors) == 1
    return sensors[0]


def test_the_automation_reads_the_mean_the_package_defines() -> None:
    """Every trigger, the hold condition and the `ppm` variable read the same
    entity, and it's the one the package creates (HA slugs the name into the
    entity id). One stray raw-sensor reference and that path skips the hold.
    """
    sensor = _statistics_sensor()
    assert sensor["entity_id"] == RAW
    assert "sensor." + sensor["name"].lower().replace(" ", "_") == MEAN
    numeric = [t for t in AUTOMATION["triggers"] if t["trigger"] == "numeric_state"]
    assert {t["entity_id"] for t in numeric} == {MEAN}
    assert MEAN in VARIABLES["ppm"]
    body = {k: v for k, v in AUTOMATION.items() if k != "description"}
    assert RAW not in yaml.safe_dump(body)


def test_the_mean_spans_ten_minutes_and_its_buffer_can_hold_them() -> None:
    """The SCD41 reports every 30 s: 10 minutes is 20 samples. A sampling_size
    below that silently shortens the window to whatever fits.
    """
    sensor = _statistics_sensor()
    assert sensor["state_characteristic"] == "mean"
    assert sensor["max_age"] == {"minutes": 10}
    assert sensor["sampling_size"] >= 2 * 20


def test_no_for_durations() -> None:
    """The hold is the mean. A `for:` resets on restarts and unavailable blips."""
    def walk(node):
        if isinstance(node, dict):
            assert "for" not in node, node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(AUTOMATION)
    walk(PACKAGE)


def test_every_non_crossing_trigger_resyncs() -> None:
    """A trigger without an id renders `deadband` as rising, but it's also
    left out of anything that checks for `resync`. Leaving Sleep was one.
    """
    for trigger in AUTOMATION["triggers"]:
        expected = {"numeric_state": None}.get(trigger["trigger"], "resync")
        if expected:
            assert trigger.get("id") == expected, trigger


def test_a_falling_crossing_never_lights_an_off_strip() -> None:
    """The guard: NOT (trigger falling AND strip off)."""
    guard = {
        "condition": "not",
        "conditions": [{"condition": "and", "conditions": [
            {"condition": "trigger", "id": "falling"},
            {"condition": "state", "entity_id": "light.kitchen_digquad", "state": "off"},
        ]}],
    }
    assert guard in AUTOMATION["conditions"]
