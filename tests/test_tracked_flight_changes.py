"""The tracked flight notifications (`automations/tracked_flight_changes.yaml`).

The delay notification has no event behind it: the Additional tracked sensor
changes on every poll, and a template picks out the delays that crossed a
step. Wrong, it either never says anything or buzzes the phone every minute,
and neither shows up anywhere but on the phone.
"""
from __future__ import annotations

import pytest
import yaml

from conftest import ROOT

AUTOMATION = yaml.safe_load((ROOT / "automations" / "tracked_flight_changes.yaml").read_text())
TRACKED = "sensor.flightradar24_additional_tracked"
SCHEDULED_ARRIVAL = 1794060000


def flight(delay_min: int | None, **extra) -> dict:
    """LX8, Zurich to Chicago, in the air with an estimated arrival."""
    return {"id": "4278a626", "flight_number": "LX8", "callsign": "SWR8T", "airport_origin_city": "Zurich",
            "airport_destination_city": "Chicago", "time_scheduled_arrival": SCHEDULED_ARRIVAL,
            "time_estimated_arrival": None if delay_min is None else SCHEDULED_ARRIVAL + delay_min * 60,
            "latitude": 47.0, **extra}


def delays(old: list[dict], new: list[dict], trigger_id: str = "delay") -> str:
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    env.filters["timestamp_custom"] = lambda value, fmt: f"<{value - SCHEDULED_ARRIVAL}s>"
    trigger = {"id": trigger_id, "from_state": {"attributes": {"flights": old}},
               "to_state": {"attributes": {"flights": new}}}
    return env.from_string(AUTOMATION["variables"]["delays"]).render(trigger=trigger)


def test_the_delay_trigger_watches_the_tracked_list() -> None:
    trigger = next(t for t in AUTOMATION["triggers"] if t.get("id") == "delay")
    assert trigger["entity_id"] == TRACKED and trigger["attribute"] == "flights"


def test_every_tracked_event_is_a_trigger() -> None:
    """The integration's four events for a tracked flight's progress."""
    events = {t["event_type"] for t in AUTOMATION["triggers"] if t["trigger"] == "event"}
    assert events == {f"flightradar24_tracked_{e}" for e in ("left_gate", "took_off", "landed", "arrived_gate")}


def test_a_poll_that_only_moves_the_plane_says_nothing() -> None:
    """Every poll changes the list: positions. That must stay quiet."""
    assert delays([flight(20)], [flight(20, latitude=47.1)]) == ""


def test_drifting_within_a_step_says_nothing() -> None:
    assert delays([flight(16)], [flight(29)]) == ""


def test_crossing_a_step_says_so() -> None:
    assert delays([flight(29)], [flight(31)]) == "LX8 Zurich → Chicago: now 31 min late, lands <1860s>"


def test_back_on_time() -> None:
    assert delays([flight(20)], [flight(5)]) == "LX8 Zurich → Chicago: back on time, lands <300s>"


def test_no_estimate_on_either_side_says_nothing() -> None:
    """After landing the estimate goes; a new flight has nothing to compare."""
    assert delays([flight(40)], [flight(None)]) == ""
    assert delays([], [flight(40)]) == ""


def test_departure_delay_before_take_off() -> None:
    """A scheduled flight has no estimated arrival yet: its departure counts."""
    def waiting(delay_min: int) -> dict:
        return {"flight_number": "LX8", "airport_origin_city": "Zurich", "airport_destination_city": "Chicago",
                "time_scheduled_departure": 1000, "time_estimated_departure": 1000 + delay_min * 60,
                "time_real_departure": None}
    assert delays([waiting(10)], [waiting(65)]) == "LX8 Zurich → Chicago: now 65 min late"


def test_events_do_not_render_the_delays() -> None:
    assert delays([flight(0)], [flight(90)], trigger_id="took_off") == ""
