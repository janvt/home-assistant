"""Every entity has an icon (icons.json) and a name (translations)."""

import json
from pathlib import Path

from homeassistant.helpers.icon import async_get_icons

from custom_components.andermatt_live.const import DOMAIN
from custom_components.andermatt_live.sensor import CAR_PARK_STATES, SENSORS

COMPONENT = Path(__file__).parent.parent / "custom_components" / DOMAIN
BINARY_SENSORS = {"open", "lift", "slope"}
SENSOR_KEYS = {d.translation_key for d in SENSORS} | {"car_park"}


async def test_every_entity_has_an_icon(hass):
    icons = (await async_get_icons(hass, "entity", [DOMAIN]))[DOMAIN]

    assert set(icons["sensor"]) == SENSOR_KEYS
    assert set(icons["binary_sensor"]) == BINARY_SENSORS


def test_every_language_names_every_entity():
    for path in (COMPONENT / "translations").glob("*.json"):
        entity = json.loads(path.read_text())["entity"]
        assert set(entity["sensor"]) == SENSOR_KEYS, path.name
        assert set(entity["binary_sensor"]) == BINARY_SENSORS, path.name
        assert set(entity["sensor"]["car_park"]["state"]) == set(CAR_PARK_STATES)
