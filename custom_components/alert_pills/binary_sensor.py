"""One binary sensor per pill: on while its condition is true.

A pill switched off in the options isn't evaluated and is unavailable. The
attributes say whether it's dismissed and whether it shows in the row.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlertPillsConfigEntry
from .const import PILL_ENTITY
from .entity import AlertPillsEntity
from .manager import PillManager, PillState


async def async_setup_entry(hass: HomeAssistant, entry: AlertPillsConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    manager = entry.runtime_data
    async_add_entities(PillSensor(manager, pill) for pill in manager.pills)


class PillSensor(AlertPillsEntity, BinarySensorEntity):
    _unrecorded_attributes = frozenset({"group", "color", "content", "critical"})

    def __init__(self, manager: PillManager, pill: dict[str, Any]) -> None:
        super().__init__(manager, pill["key"], PILL_ENTITY.format(key=pill["key"]))
        self.key = pill["key"]
        self._watch = {self.key}
        self._attr_name = pill["name"]
        self._attr_icon = pill["icon"]

    @property
    def _pill(self) -> PillState:
        return self.manager.states.get(self.key) or PillState()

    @property
    def available(self) -> bool:
        return self._pill.on is not None

    @property
    def is_on(self) -> bool | None:
        return self._pill.on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pill = self.manager.by_key[self.key]
        return {
            "group": pill["group"],
            "color": self._pill.color,
            "content": self._pill.content,
            "critical": pill.get("critical", False),
            "dismissed": self.manager.is_dismissed(self.key),
            "in_row": self.key not in self.manager.card_only,
        }
