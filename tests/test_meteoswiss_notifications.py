"""The MeteoSwiss notifications (`automations/meteoswiss_weather_notifications.yaml`).

They use the MeteoSwiss integration's own triggers (v2.3.0). Wrong, they fail
quietly: a trigger id without a branch fires and sends nothing, a sensor id
that drifts from the pills' watches a sensor that isn't there, and the
warning's message renders empty on the phone.
"""
from __future__ import annotations

import re
import runpy
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from conftest import ROOT

AUTOMATION = yaml.safe_load((ROOT / "automations" / "meteoswiss_weather_notifications.yaml").read_text())
PILLS = runpy.run_path(str(ROOT / "dashboards" / "mobile-alerts" / "pills.py"))
TRIGGERS = {t["id"]: t for t in AUTOMATION["triggers"]}

# From the integration's triggers.yaml (janvt/homeassistant-meteoswiss v2.3.0-beta.1).
OPTIONS = {
    "warning_reached": {"level": {"yellow", "orange", "red"}},
    "hail_expected": {"probability": range(1, 101)},
    "foehn_expected": {"outlook": {"south", "strong_south", "north", "strong_north"}},
    "rain_started": {"rate": None},
    "rain_stopped": {"rate": None},
}


def test_every_trigger_is_one_meteoswiss_has() -> None:
    """HA refuses an automation over an unknown trigger or option value."""
    for t in AUTOMATION["triggers"]:
        domain, _, name = t["trigger"].partition(".")
        assert domain == "meteoswiss" and name in OPTIONS, t["trigger"]
        for key, value in t.get("options", {}).items():
            allowed = OPTIONS[name][key]
            assert allowed is None or value in allowed, f"{t['id']}: {key}={value!r}"


def test_every_trigger_has_a_branch() -> None:
    """A trigger whose id no branch picks runs and sends nothing."""
    branches = {c["id"] for o in AUTOMATION["actions"][0]["choose"] for c in o["conditions"]
                if c["condition"] == "trigger"}
    assert branches == set(TRIGGERS)


def test_triggers_watch_the_pills_sensors() -> None:
    """The notifications and the pills say the same thing about the same
    sensors: a sensor renamed in one place is caught here."""
    assert TRIGGERS["warning"]["target"]["entity_id"] == PILLS["WARN_HOME"]
    assert TRIGGERS["hail"]["target"]["entity_id"] == PILLS["RADAR_HAIL"]
    assert TRIGGERS["foehn"]["target"]["entity_id"] == PILLS["FOHN_OUTLOOK"]


def test_hail_threshold_is_the_pills() -> None:
    hail = next(p for p in PILLS["ALERTS"] if p["key"] == "hail")
    threshold = int(re.search(r">= (\d+)", hail["tmpl"]).group(1))
    assert TRIGGERS["hail"]["options"]["probability"] == threshold


def test_messages_read_only_the_pills_sensors() -> None:
    """A message reading a sensor nobody else reads is the first to go stale."""
    known = {PILLS["WARN_HOME"], PILLS["RADAR_HAIL"], PILLS["RADAR_HAIL_SIZE"], PILLS["FOHN_OUTLOOK"],
             PILLS["FOHN_DIFF"]}
    used = set(re.findall(r"sensor\.[a-z0-9_]+", yaml.safe_dump(AUTOMATION["actions"])))
    assert used <= known, sorted(used - known)


def _warning_message(warnings: list[dict]) -> str:
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment()
    env.filters["as_datetime"] = lambda s: datetime.fromisoformat(s)
    env.filters["as_local"] = lambda d: d
    branch = AUTOMATION["actions"][0]["choose"][0]["sequence"][0]
    now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    return env.from_string(branch["data"]["message"]).render(
        state_attr=lambda e, a: warnings, now=lambda: now).strip()


def _warning(level: str, start_h: int, end_h: int, event: str = "Wind") -> dict:
    base = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    return {"event": event, "level": level, "onset": (base + timedelta(hours=start_h)).isoformat(),
            "expires": (base + timedelta(hours=end_h)).isoformat()}


def test_warning_message_lists_only_orange_and_red() -> None:
    """The yellow ones are the pill's, not a buzz on the phone."""
    message = _warning_message([_warning("yellow", 0, 6, "Rain"), _warning("orange", 3, 9)])
    assert message == "Wind (orange), Tue 15:00 to Tue 21:00"


def test_warning_in_force_says_until() -> None:
    assert _warning_message([_warning("red", -1, 4)]) == "Wind (red), until Tue 16:00"


def test_warning_message_is_never_empty() -> None:
    assert _warning_message([]) == "See the Weather dashboard."
