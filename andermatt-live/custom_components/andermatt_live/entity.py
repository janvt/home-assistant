"""The device of a sector, which all its entities share."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.andermatt_live import AndermattLiveCoordinator
from custom_components.andermatt_live.const import ATTRIBUTION, DOMAIN, MANUFACTURER
from custom_components.andermatt_live.live import PAGE_URL, SECTORS, Sector


class SectorEntity(CoordinatorEntity[AndermattLiveCoordinator]):
    """An entity of a sector.  Its unique id is the sector's slug and a key,
    which must not change, or the entity would lose its settings and history."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self, coordinator: AndermattLiveCoordinator, slug: str, key: str
    ) -> None:
        super().__init__(coordinator)
        self.slug = slug
        self._attr_unique_id = f"{slug}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, slug)},
            name=SECTORS.get(slug, slug),
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=PAGE_URL.format(page="start", sector=slug),
        )

    @property
    def sector(self) -> Sector | None:
        return self.coordinator.data.get(self.slug)

    @property
    def available(self) -> bool:
        return super().available and self.sector is not None
