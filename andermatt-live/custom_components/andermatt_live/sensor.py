"""Counts of open lifts and slopes, the snow, and the car parks of a sector."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from custom_components.andermatt_live import (
    AndermattLiveConfigEntry,
    AndermattLiveCoordinator,
)
from custom_components.andermatt_live.entity import SectorEntity
from custom_components.andermatt_live.live import CarPark, Sector

CAR_PARK_STATES = ["free", "full"]


@dataclass(frozen=True, kw_only=True)
class SectorSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Sector], float | int | None]
    attributes_fn: Callable[[Sector], dict[str, Any]] | None = None


SENSORS = (
    SectorSensorDescription(
        key="lifts_open",
        translation_key="lifts_open",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.lifts_open if s.lifts else None,
        attributes_fn=lambda s: {"total": len(s.lifts)},
    ),
    SectorSensorDescription(
        key="slopes_open",
        translation_key="slopes_open",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.slopes_open if s.slopes else None,
        attributes_fn=lambda s: {"total": len(s.slopes)},
    ),
    SectorSensorDescription(
        key="slopes_open_length",
        translation_key="slopes_open_length",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value_fn=lambda s: s.slopes_open_length if s.slopes else None,
        attributes_fn=lambda s: {
            "total": sum(slope.length or 0 for slope in s.slopes.values())
        },
    ),
    SectorSensorDescription(
        key="snow_depth",
        translation_key="snow_depth",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        suggested_display_precision=0,
        value_fn=lambda s: s.snow_depth,
    ),
    SectorSensorDescription(
        key="new_snow",
        translation_key="new_snow",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        suggested_display_precision=0,
        value_fn=lambda s: s.new_snow,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AndermattLiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for slug, sector in coordinator.data.items():
        entities.extend(SectorSensor(coordinator, slug, d) for d in SENSORS)
        entities.extend(
            CarParkSensor(coordinator, slug, car_park)
            for car_park in sector.car_parks.values()
        )
    async_add_entities(entities)


class SectorSensor(SectorEntity, SensorEntity):
    entity_description: SectorSensorDescription

    def __init__(
        self,
        coordinator: AndermattLiveCoordinator,
        slug: str,
        description: SectorSensorDescription,
    ) -> None:
        super().__init__(coordinator, slug, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | None:
        return self.entity_description.value_fn(self.sector) if self.sector else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attributes_fn
        return fn(self.sector) if fn and self.sector else None


class CarParkSensor(SectorEntity, SensorEntity):
    """Free or full; "full" also covers a car park that is closed."""

    _attr_translation_key = "car_park"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = CAR_PARK_STATES

    def __init__(
        self, coordinator: AndermattLiveCoordinator, slug: str, car_park: CarPark
    ) -> None:
        super().__init__(coordinator, slug, f"car_park_{car_park.key}")
        self.key = car_park.key
        self._attr_name = car_park.name

    @property
    def car_park(self) -> CarPark | None:
        return self.sector.car_parks.get(self.key) if self.sector else None

    @property
    def available(self) -> bool:
        return super().available and self.car_park is not None

    @property
    def native_value(self) -> str | None:
        if (car_park := self.car_park) is None or car_park.free is None:
            return None
        return "free" if car_park.free else "full"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {"text": self.car_park.text} if self.car_park else None
