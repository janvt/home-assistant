"""Lifecycle of Andermatt Live."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from custom_components.andermatt_live.const import (
    CONF_SECTORS,
    DOMAIN,
    UPDATE_INTERVAL,
    USER_AGENT,
)
from custom_components.andermatt_live.live import (
    AndermattLiveClient,
    AndermattLiveError,
    Sector,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type AndermattLiveConfigEntry = ConfigEntry[AndermattLiveCoordinator]


def settings(entry: ConfigEntry) -> dict[str, Any]:
    """The sectors: set up with the entry, then changed in the options."""
    return {**entry.data, **entry.options}


class AndermattLiveCoordinator(TimestampDataUpdateCoordinator[dict[str, Sector]]):
    """The followed sectors, by slug; with the time of the last update that
    succeeded."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AndermattLiveConfigEntry,
        client: AndermattLiveClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.sectors: list[str] = settings(entry)[CONF_SECTORS]

    async def _async_update_data(self) -> dict[str, Sector]:
        try:
            return await self.client.async_sectors(self.sectors)
        except AndermattLiveError as err:
            raise UpdateFailed(str(err)) from err


async def async_setup_entry(
    hass: HomeAssistant, entry: AndermattLiveConfigEntry
) -> bool:
    client = AndermattLiveClient(async_get_clientsession(hass), USER_AGENT)
    coordinator = AndermattLiveCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _remove_unselected_devices(hass, entry)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _remove_unselected_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the sectors taken out in the options, with their entities."""
    selected = set(settings(entry)[CONF_SECTORS])
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        slugs = {slug for domain, slug in device.identifiers if domain == DOMAIN}
        if not slugs & selected:
            registry.async_remove_device(device.id)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload with the new sectors."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: AndermattLiveConfigEntry
) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
