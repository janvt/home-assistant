"""The count of shown pills, and what the dashboard row shows.

`sensor.weather_alerts_active`: pills on, switched on and not dismissed.
`sensor.alert_pills_row`: how many of the row's places are in use; its
`slots` attribute has each place's icon, colour and content, the last one "+N"
when more pills are on than fit.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlertPillsConfigEntry
from .const import COUNT_ENTITY, ROW_ENTITY
from .entity import AlertPillsEntity


async def async_setup_entry(hass: HomeAssistant, entry: AlertPillsConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    manager = entry.runtime_data
    if manager.pills:  # nothing to count before the first `alert_pills.load`
        async_add_entities([CountSensor(manager, "active", COUNT_ENTITY), RowSensor(manager, "row", ROW_ENTITY)])


class CountSensor(AlertPillsEntity, SensorEntity):
    _attr_name = "Weather alerts active"
    _attr_icon = "mdi:bell-ring-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"shown"})

    @property
    def native_value(self) -> int:
        return len(self.manager.shown)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"shown": self.manager.shown}


class RowSensor(AlertPillsEntity, SensorEntity):
    _attr_name = "Alert pills row"
    _attr_icon = "mdi:dots-horizontal"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unrecorded_attributes = frozenset({"slots", "places"})

    @property
    def native_value(self) -> int:
        return len(self.manager.slots())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"slots": self.manager.slots(), "places": self.manager.places}
