"""Platform for sensor integration that creates multiple entities from a coordinator dict."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN  # Make sure you have DOMAIN defined in const.py

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
    coordinator: DataUpdateCoordinator[dict[str, dict[any, any]]] = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Create a sensor entity for each key in the coordinator data dict.
    keys = coordinator.data.get("climate_data", {}).keys()
    _LOGGER.debug("Creating %s sensors", len(keys))
    entities = [TemperatureSensor(coordinator, name) for name in keys]
    async_add_entities(entities)

    # Remove entities and devices that are no longer in the configuration
    # await _async_cleanup_entities_and_devices(hass, entry, current_unique_ids)
    await coordinator.async_refresh()

class TemperatureSensor(CoordinatorEntity, SensorEntity):
    """A sensor entity that represents the temperature for a given name from the coordinator data."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    def __init__(self, coordinator: DataUpdateCoordinator, name: str) -> None:
        """Initialize the sensor with the coordinator and the specific name key."""
        super().__init__(coordinator)
        self._name = name
        # You may want to create a unique ID if you have a unique identifier available.
        # For demo purposes, we'll just base it on the name.
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{name}"

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