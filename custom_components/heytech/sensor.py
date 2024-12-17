"""Platform for sensor integration that creates multiple entities from a coordinator dict."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN  # Make sure you have DOMAIN defined in const.py
from .data import IntegrationHeytechConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """
    Set up sensors for the given config entry.
    The coordinator should store data as a dict, e.g.:
    coordinator.data = {
        "living_room": 20.5,
        "kitchen": 21.3,
        ...
    }
    """
    coordinator: DataUpdateCoordinator[dict[str, dict[any, any]]] = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinator"]

    # Create a sensor entity for each key in the coordinator data dict.
    keys = coordinator.data.get("climate_data", {}).keys()
    _LOGGER.debug("Creating %s sensors", len(keys))
    entities = []
    current_unique_ids: set[str] = set()
    for name in keys:
        unique_id = f"{entry.entry_id}_{name}"
        current_unique_ids.add(unique_id)
        if "brightness" in name:
            entity = HeytechBrightnessSensor(coordinator, name, unique_id)
        elif "wind" in name:
            entity = HeytechWindSensor(coordinator, name, unique_id)
        elif "alarm" in name or "rain" in name:
            entity = HeytechBinarySensor(coordinator, name, unique_id)
        elif "humidity" in name:
            entity = HeytechHumiditySensor(coordinator, name, unique_id)
        else:
            entity = HeytechTemperatureSensor(coordinator, name, unique_id)
        entities.append(entity)
    async_add_entities(entities)

    # Remove entities and devices that are no longer in the configuration
    await _async_cleanup_entities_and_devices(hass, entry, current_unique_ids)
    await coordinator.async_refresh()


class HeytechBrightnessSensor(CoordinatorEntity, SensorEntity):
    """A sensor entity that represents the brightness for a given name from the coordinator data."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = "lx"

    def __init__(
        self, coordinator: DataUpdateCoordinator, name: str, unique_id: str
    ) -> None:
        """Initialize the sensor with the coordinator and the specific name key."""
        super().__init__(coordinator)
        self._name = name
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name.capitalize().replace('_', ' ')}"

    @property
    def native_value(self) -> float | None:
        """
        Return the current brightness value.

        If the coordinator does not have data for this name,
        it should return None or handle it gracefully.
        """
        # coordinator.data is a dict with keys as names and values as brightness.
        value = self.coordinator.data.get("climate_data", {}).get(self._name)
        _LOGGER.debug("Sensor %s has value %s", self._name, value)
        return float(value) if value is not None else None


class HeytechWindSensor(CoordinatorEntity, SensorEntity):
    """A sensor entity that represents the wind speed for a given name from the coordinator data."""

    _attr_device_class = SensorDeviceClass.WIND_SPEED
    _attr_native_unit_of_measurement = "km/h"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id,
    ) -> None:
        """Initialize the sensor with the coordinator and the specific name key."""
        super().__init__(coordinator)
        self._name = name
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name.capitalize().replace('_', ' ')}"

    @property
    def native_value(self) -> float | None:
        """
        Return the current wind speed value.

        If the coordinator does not have data for this name,
        it should return None or handle it gracefully.
        """
        # coordinator.data is a dict with keys as names and values as wind speeds.
        value = self.coordinator.data.get("climate_data", {}).get(self._name)
        _LOGGER.debug("Sensor %s has value %s", self._name, value)
        return float(value) if value is not None else None


class HeytechTemperatureSensor(CoordinatorEntity, SensorEntity):
    """A sensor entity that represents the temperature for a given name from the coordinator data."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id,
    ) -> None:
        """Initialize the sensor with the coordinator and the specific name key."""
        super().__init__(coordinator)
        self._name = name
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name.capitalize().replace('_', ' ')}"

    @property
    def native_value(self) -> float | None:
        """
        Return the current temperature value.

        If the coordinator does not have data for this name,
        it should return None or handle it gracefully.
        """
        # coordinator.data is a dict with keys as names and values as temperatures.
        value = self.coordinator.data.get("climate_data", {}).get(self._name)
        _LOGGER.debug("Sensor %s has value %s", self._name, value)
        return float(value) if value is not None else None


class HeytechHumiditySensor(CoordinatorEntity, SensorEntity):
    """A sensor entity that represents the humidity for a given name from the coordinator data."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id,
    ) -> None:
        """Initialize the sensor with the coordinator and the specific name key."""
        super().__init__(coordinator)
        self._name = name
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name.capitalize().replace('_', ' ')}"

    @property
    def native_value(self) -> float | None:
        """
        Return the current humidity value.

        If the coordinator does not have data for this name,
        it should return None or handle it gracefully.
        """
        # coordinator.data is a dict with keys as names and values as humidity.
        value = self.coordinator.data.get("climate_data", {}).get(self._name)
        _LOGGER.debug("Sensor %s has value %s", self._name, value)
        return float(value) if value is not None else None


class HeytechBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A binary sensor entity that represents the alarm state for a given name from the coordinator data."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, name: str, unique_id
    ) -> None:
        """Initialize the sensor with the coordinator and the specific name key."""
        super().__init__(coordinator)
        self._name = name
        # You may want to create a unique ID if you have a unique identifier available.
        # For demo purposes, we'll just base it on the name.
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._name.capitalize().replace('_', ' ')}"

    @property
    def is_on(self) -> bool:
        """
        Return the alarm state.

        If the coordinator does not have data for this name,
        it should return None or handle it gracefully.
        """
        # coordinator.data is a dict with keys as names and values as alarm states.
        value = self.coordinator.data.get("climate_data", {}).get(self._name)
        _LOGGER.debug("Binary sensor %s has value %s", self._name, value)
        return (value == "1" or value == 1) if value is not None else False


async def _async_cleanup_entities_and_devices(
    hass: HomeAssistant,
    entry: IntegrationHeytechConfigEntry,
    current_unique_ids: set[str],
) -> None:
    """Remove entities that are no longer in the configuration."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    # Map devices to their associated entities
    device_entities: dict[str, list[er.RegistryEntry]] = {}

    for entity_entry in entries:
        if entity_entry.domain != "sensor":
            continue

        device_id = entity_entry.device_id
        if device_id:
            device_entities.setdefault(device_id, []).append(entity_entry)

        if entity_entry.unique_id not in current_unique_ids:
            _LOGGER.info(
                "Removing entity %s (%s)",
                entity_entry.entity_id,
                entity_entry.unique_id,
            )
            entity_registry.async_remove(entity_entry.entity_id)

    # Remove devices that have no entities left
    for device_id, entities in device_entities.items():
        # Check if any entities associated with the device still exist
        remaining_entities = [
            e for e in entities if entity_registry.async_get(e.entity_id) is not None
        ]
        if not remaining_entities:
            # No entities left for this device; remove the device
            device_entry = device_registry.async_get(device_id)
            if device_entry:
                _LOGGER.info(
                    "Removing device %s (%s)", device_entry.name, device_entry.id
                )
                device_registry.async_remove_device(device_id)
