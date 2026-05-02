"""Sensor entities for Reef Factory KH Keeper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN
from .coordinator import ReefFactoryKHCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class KHSensorDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a data key."""
    data_key: str = ""


SENSORS: tuple[KHSensorDescription, ...] = (
    KHSensorDescription(
        key="latest_kh",
        data_key="latest_kh",
        name="KH Value",
        native_unit_of_measurement="dKH",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:water-check",
    ),
    KHSensorDescription(
        key="reagent_ml",
        data_key="reagent_ml",
        name="Reagent Remaining",
        native_unit_of_measurement="mL",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:beaker-outline",
        suggested_display_precision=2,
    ),
    KHSensorDescription(
        key="last_measurement",
        data_key="last_measurement",
        name="Last Measurement",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
    KHSensorDescription(
        key="alarm_low",
        data_key="alarm_low",
        name="KH Alarm Low",
        native_unit_of_measurement="dKH",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:arrow-down-circle-outline",
        entity_registry_enabled_default=False,
    ),
    KHSensorDescription(
        key="alarm_high",
        data_key="alarm_high",
        name="KH Alarm High",
        native_unit_of_measurement="dKH",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:arrow-up-circle-outline",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ReefFactoryKHCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KHSensorEntity(coordinator, description, entry)
        for description in SENSORS
    )


class KHSensorEntity(CoordinatorEntity[ReefFactoryKHCoordinator], SensorEntity):
    """A sensor entity backed by the KH Keeper coordinator."""

    entity_description: KHSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ReefFactoryKHCoordinator,
        description: KHSensorDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        serial = entry.data[CONF_SERIAL]
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"KH Keeper {serial}",
            manufacturer="Reef Factory",
            model="KH Keeper Plus",
        )

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self.entity_description.data_key)
        if value is None:
            return None
        # TIMESTAMP device class expects a datetime string in ISO format
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            from datetime import datetime, timezone
            try:
                dt = datetime.fromisoformat(str(value))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                return None
        return value
