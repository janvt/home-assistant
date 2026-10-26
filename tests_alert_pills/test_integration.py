"""What the dashboard relies on: entity ids, the count, the row, and the options
from the phone. Each test names the quiet failure it guards against.
"""
from __future__ import annotations

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.alert_pills.const import DOMAIN

COUNT, ROW = "sensor.weather_alerts_active", "sensor.alert_pills_row"


def pill(key: str, group: str = "Home", **extra) -> dict:
    return {"key": key, "name": key.replace("_", " ").title(), "group": group, "icon": "mdi:alert",
            "color": "orange", "state": f"{{{{ is_state('input_boolean.{key}', 'on') }}}}", **extra}


PILLS = [
    pill("smoke", "Safety", critical=True, color="red"),
    pill("fohn", "Weather", color="{{ 'red' if is_state('input_boolean.storm', 'on') else 'orange' }}"),
    pill("trains", "Travel", content="{{ states('sensor.trains') }}"),
    pill("rain", "Weather"),
    pill("music"),
]
GROUPS = ["Safety", "Weather", "Travel", "Home"]


async def setup(hass: HomeAssistant, pills: list[dict] = PILLS):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await load(hass, pills)
    return hass.config_entries.async_get_entry(entry.entry_id)


async def load(hass: HomeAssistant, pills: list[dict], dry_run: bool = False) -> dict:
    response = await hass.services.async_call(DOMAIN, "load", {"pills": pills, "groups": GROUPS, "dry_run": dry_run},
                                              blocking=True, return_response=True)
    await hass.async_block_till_done()
    return response


async def turn(hass: HomeAssistant, key: str, on: bool) -> None:
    hass.states.async_set(f"input_boolean.{key}", "on" if on else "off")
    await hass.async_block_till_done()


def count(hass: HomeAssistant) -> int:
    return int(hass.states.get(COUNT).state)


def slots(hass: HomeAssistant) -> list[dict]:
    return hass.states.get(ROW).attributes["slots"]


async def options(hass: HomeAssistant, entry, **values) -> None:
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["type"] == "form"
    data = {"disabled": [], "disabled_groups": [], "card_only": [], "places": 6, **values}
    result = await hass.config_entries.options.async_configure(flow["flow_id"], data)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()


async def test_entity_ids_match_the_old_helpers(hass: HomeAssistant) -> None:
    """The dashboard, history and pills reading other pills all use these ids."""
    await setup(hass)
    for p in PILLS:
        assert hass.states.get(f"binary_sensor.pill_{p['key']}") is not None, p["key"]
    assert hass.states.get(COUNT) is not None and hass.states.get(ROW) is not None


async def test_no_entities_before_the_first_load(hass: HomeAssistant) -> None:
    """The count sensor would grab `sensor.weather_alerts_active_2` while the old
    template helper still holds the id: nothing exists until pills arrive."""
    await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids() == []


async def test_a_second_entry_is_refused(hass: HomeAssistant) -> None:
    await setup(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "abort"


async def test_pills_follow_their_templates(hass: HomeAssistant) -> None:
    await setup(hass)
    assert count(hass) == 0 and slots(hass) == []
    hass.states.async_set("sensor.trains", "12")
    await turn(hass, "trains", True)
    await turn(hass, "fohn", True)
    assert hass.states.get("binary_sensor.pill_fohn").state == "on"
    assert count(hass) == 2
    # Row order is pills.py order, not the order they turned on.
    assert [s["key"] for s in slots(hass)] == ["fohn", "trains"]
    assert slots(hass)[1]["content"] == "12"
    assert slots(hass)[0]["color"] == "orange"
    await turn(hass, "storm", True)
    assert slots(hass)[0]["color"] == "red"
    await turn(hass, "fohn", False)
    assert count(hass) == 1


async def test_dismissed_pills_leave_the_row_until_they_turn_on_again(hass: HomeAssistant) -> None:
    await setup(hass)
    await turn(hass, "rain", True)
    await hass.services.async_call(DOMAIN, "toggle_dismiss", {"key": "rain"}, blocking=True)
    await hass.async_block_till_done()
    assert count(hass) == 0 and slots(hass) == []
    assert hass.states.get("binary_sensor.pill_rain").attributes["dismissed"] is True
    await turn(hass, "rain", False)
    await turn(hass, "rain", True)
    assert count(hass) == 1, "a dismissed pill comes back the next time it turns on"


async def test_hold_again_brings_a_pill_back(hass: HomeAssistant) -> None:
    await setup(hass)
    await turn(hass, "rain", True)
    for _ in range(2):
        await hass.services.async_call(DOMAIN, "toggle_dismiss", {"key": "rain"}, blocking=True)
    await hass.async_block_till_done()
    assert count(hass) == 1


async def test_safety_pills_cannot_be_dismissed(hass: HomeAssistant) -> None:
    await setup(hass)
    await turn(hass, "smoke", True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "toggle_dismiss", {"key": "smoke"}, blocking=True)
    assert count(hass) == 1


async def test_dismissal_survives_a_reload(hass: HomeAssistant) -> None:
    """The old setup lost dismissals on restart: template sensors forget when
    they last turned on."""
    entry = await setup(hass)
    await turn(hass, "rain", True)
    await hass.services.async_call(DOMAIN, "dismiss", {"key": "rain"}, blocking=True)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.pill_rain").state == "on"
    assert count(hass) == 0


async def test_switched_off_pills_never_show(hass: HomeAssistant) -> None:
    entry = await setup(hass)
    await turn(hass, "rain", True)
    await turn(hass, "music", True)
    await options(hass, entry, disabled=["rain"])
    assert hass.states.get("binary_sensor.pill_rain").state == STATE_UNAVAILABLE
    assert count(hass) == 1
    await options(hass, entry)
    assert count(hass) == 2, "switching it back on evaluates it again"


async def test_switched_off_groups(hass: HomeAssistant) -> None:
    entry = await setup(hass)
    for key in ("fohn", "rain", "music"):
        await turn(hass, key, True)
    await options(hass, entry, disabled_groups=["Weather"])
    assert count(hass) == 1
    assert [s["key"] for s in slots(hass)] == ["music"]


async def test_card_only_pills_count_but_take_no_place(hass: HomeAssistant) -> None:
    entry = await setup(hass)
    await turn(hass, "rain", True)
    await turn(hass, "music", True)
    await options(hass, entry, card_only=["rain"])
    assert count(hass) == 2
    assert [s["key"] for s in slots(hass)] == ["music"]
    assert hass.states.get("binary_sensor.pill_rain").attributes["in_row"] is False


async def test_row_size_and_overflow(hass: HomeAssistant) -> None:
    entry = await setup(hass)
    for key in ("fohn", "trains", "rain", "music"):
        await turn(hass, key, True)
    await options(hass, entry, places=3)
    assert [s["content"] if not s["key"] else s["key"] for s in slots(hass)] == ["fohn", "trains", "+2"]
    assert hass.states.get(ROW).state == "3"
    await options(hass, entry, places=4)
    assert [s["key"] for s in slots(hass)] == ["fohn", "trains", "rain", "music"]


async def test_dry_run_changes_nothing(hass: HomeAssistant) -> None:
    await setup(hass)
    response = await load(hass, PILLS[:-1], dry_run=True)
    assert response["removed"] == ["music"]
    assert hass.states.get("binary_sensor.pill_music") is not None


async def test_dropped_pills_lose_their_entities(hass: HomeAssistant) -> None:
    await setup(hass)
    response = await load(hass, [*PILLS[:-1], pill("new_one")])
    assert response["removed"] == ["music"] and response["added"] == ["new_one"]
    registry = er.async_get(hass)
    assert registry.async_get("binary_sensor.pill_music") is None
    assert hass.states.get("binary_sensor.pill_new_one") is not None


async def test_a_broken_template_is_refused(hass: HomeAssistant) -> None:
    """A Jinja typo used to show up only as a helper that stayed unavailable."""
    await setup(hass)
    with pytest.raises(ServiceValidationError):
        await load(hass, [pill("broken", state="{{ is_state('x', 'on' }}")])
    assert hass.states.get("binary_sensor.pill_rain") is not None


async def test_unload(hass: HomeAssistant) -> None:
    entry = await setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_the_real_pills_load(hass: HomeAssistant) -> None:
    """Every pill in pills.py passes the load schema, compiles and gets its id."""
    import runpy
    from pathlib import Path

    build = runpy.run_path(str(Path(__file__).resolve().parents[1] / "dashboards" / "mobile-alerts" / "build.py"))
    defs = build["definitions"]()
    await setup(hass, defs["pills"])
    for p in defs["pills"]:
        assert hass.states.get(f"binary_sensor.pill_{p['key']}") is not None, p["key"]
