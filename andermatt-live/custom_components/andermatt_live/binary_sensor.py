"""Whether the sector, each lift and each slope is open, for automations."""

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from custom_components.andermatt_live import (
    AndermattLiveConfigEntry,
    AndermattLiveCoordinator,
)
from custom_components.andermatt_live.entity import SectorEntity
from custom_components.andermatt_live.live import Lift, Slope


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AndermattLiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """The lifts and slopes the site lists now; one it adds later appears
    when the entry is reloaded."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for slug, sector in coordinator.data.items():
        entities.append(SectorOpenSensor(coordinator, slug))
        entities.extend(
            LiftSensor(coordinator, slug, lift) for lift in sector.lifts.values()
        )
        entities.extend(
            SlopeSensor(coordinator, slug, slope) for slope in sector.slopes.values()
        )
    async_add_entities(entities)


class SectorOpenSensor(SectorEntity, BinarySensorEntity):
    """On while at least one of the sector's lifts runs."""

    _attr_translation_key = "open"

    def __init__(self, coordinator: AndermattLiveCoordinator, slug: str) -> None:
        super().__init__(coordinator, slug, "open")

    @property
    def is_on(self) -> bool | None:
        if (sector := self.sector) is None or not sector.lifts:
            return None
        return sector.lifts_open > 0


class LiftSensor(SectorEntity, BinarySensorEntity):
    _attr_translation_key = "lift"

    def __init__(
        self, coordinator: AndermattLiveCoordinator, slug: str, lift: Lift
    ) -> None:
        super().__init__(coordinator, slug, f"lift_{lift.key}")
        self.key = lift.key
        # The site's own name, "14 Gurschen-Bahn", in every language.
        self._attr_name = lift.name

    @property
    def lift(self) -> Lift | None:
        """None if the lift is no longer on the site."""
        return self.sector.lifts.get(self.key) if self.sector else None

    @property
    def available(self) -> bool:
        return super().available and self.lift is not None

    @property
    def is_on(self) -> bool | None:
        return self.lift.is_open if self.lift else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (lift := self.lift) is None:
            return None
        return {
            "number": lift.number,
            "kind": lift.kind,
            "status": lift.status,
            "first_ride": lift.first_ride,
            "last_ride": lift.last_ride,
        }


class SlopeSensor(SectorEntity, BinarySensorEntity):
    """Off by default: a sector has up to 30 slopes, and the counts on the
    sector are what most people need."""

    _attr_translation_key = "slope"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: AndermattLiveCoordinator, slug: str, slope: Slope
    ) -> None:
        super().__init__(coordinator, slug, f"slope_{slope.key}")
        self.key = slope.key
        self._attr_name = slope.name

    @property
    def slope(self) -> Slope | None:
        return self.sector.slopes.get(self.key) if self.sector else None

    @property
    def available(self) -> bool:
        return super().available and self.slope is not None

    @property
    def is_on(self) -> bool | None:
        return self.slope.is_open if self.slope else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (slope := self.slope) is None:
            return None
        return {
            "number": slope.number,
            "status": slope.status,
            "difficulty": slope.difficulty,
            "length": slope.length,
        }
