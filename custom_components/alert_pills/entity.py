"""The base all alert pill entities share: one device, updates from the manager."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import PillManager


class AlertPillsEntity(Entity):
    _attr_should_poll = False
    # Only these pills' changes redraw the entity; None: every change does.
    _watch: set[str] | None = None

    def __init__(self, manager: PillManager, unique_id: str, entity_id: str) -> None:
        self.manager = manager
        self._attr_unique_id = unique_id
        self.entity_id = entity_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, manager.entry.entry_id)}, name="Alert pills",
                                            entry_type=DeviceEntryType.SERVICE)

    async def async_added_to_hass(self) -> None:
        def changed(keys: set[str] | None) -> None:
            if keys is None or self._watch is None or keys & self._watch:
                self.async_write_ha_state()

        self.async_on_remove(self.manager.async_add_listener(changed))
