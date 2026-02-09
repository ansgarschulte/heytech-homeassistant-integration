"""
Platform for sensor integration.

that creates multiple entities from a coordinator dict.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN  # Make sure you have DOMAIN defined in const.py

LUX_10 = 10

LUX_136 = 136

LUX_36 = 36

LUX_28 = 28

LUX_19 = 19

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    }.
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

    # Add automation status sensor
    automation_unique_id = f"{entry.entry_id}_automation_status"
    current_unique_ids.add(automation_unique_id)
    entities.append(
        HeytechAutomationStatusSensor(
            coordinator, "automation_status", automation_unique_id
        )
    )

    # Add logbook count sensor
    logbook_unique_id = f"{entry.entry_id}_logbook_count"
    current_unique_ids.add(logbook_unique_id)
    entities.append(
        HeytechLogbookCountSensor(coordinator, "logbook_count", logbook_unique_id)
    )

    # Add system info sensors
    system_info_keys = ["model", "firmware", "device_number"]
    for key in system_info_keys:
        unique_id = f"{entry.entry_id}_system_{key}"
        current_unique_ids.add(unique_id)
        entities.append(HeytechSystemInfoSensor(coordinator, key, unique_id))

    async_add_entities(entities)

    # Remove entities and devices that are no longer in the configuration
    await _async_cleanup_entities_and_devices(hass, entry, current_unique_ids)
    await coordinator.async_refresh()


def calculate_lux_value_based_on_heytech(value: float) -> float:
    """Calculate the lux value based on the Heytech value."""
    if value < LUX_10:  # LuxPrefix = 0 --> Lux-Wert n steht für 0.1 ... 0.9 Lux
        lux_prefix = 0
        lux = value
    elif value <= LUX_19:  # LuxPrefix = 1 --> Lux-Wert n steht für 1 ... 900 Lux
        lux_prefix = 1
        lux = value - 9
    elif value <= LUX_28:
        lux_prefix = 1
        lux = (value - 20) * 10 + 20
    elif value <= LUX_36:
        lux_prefix = 1
        lux = (value - 29) * 100 + 200
    elif value <= LUX_136:  # LuxPrefix = 2 --> Lux-Wert n steht für 1 ... 900 kLux
        lux_prefix = 2
        lux = value - 36
    else:
        lux_prefix = 2
        lux = (value - 137) * 10 + 110

    if lux_prefix == 0:
        result_lux = 1 - (10 - lux) / 10
    elif lux_prefix == 1:
        result_lux = lux
    else:  # lux_prefix == 2
        result_lux = lux * 1000

    return result_lux


class HeytechBrightnessSensor(CoordinatorEntity, SensorEntity):
    """A sensor entity that represents the brightness for a given name."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = "lx"

    def __init__(
        self, coordinator: DataUpdateCoordinator, name: str, unique_id: str
    ) -> None:
        """Initialize the sensor with the coordinator and name."""
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
        return (
            calculate_lux_value_based_on_heytech(float(value))
            if value is not None
            else None
        )


class HeytechWindSensor(CoordinatorEntity, SensorEntity):
    """A sensor entity that represents the wind speed for a given name."""

    _attr_device_class = SensorDeviceClass.WIND_SPEED
    _attr_native_unit_of_measurement = "km/h"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id: str,
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
    """A sensor entity that represents the temperature for a given name."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id: str,
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
    """A sensor entity that represents the humidity for a given name."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = "%"

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
        Return the current humidity value.

        If the coordinator does not have data for this name,
        it should return None or handle it gracefully.
        """
        # coordinator.data is a dict with keys as names and values as humidity.
        value = self.coordinator.data.get("climate_data", {}).get(self._name)
        _LOGGER.debug("Sensor %s has value %s", self._name, value)
        return float(value) if value is not None else None


class HeytechBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor entity represents the alarm state for a given name."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, name: str, unique_id: str
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
        return (value in ("1", 1)) if value is not None else False


class HeytechAutomationStatusSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for external automation switch status."""

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
        return "Automation Status"

    @property
    def is_on(self) -> bool:
        """
        Return the automation status.

        True if external automation is enabled, False otherwise.
        """
        value = self.coordinator.data.get("automation_status")
        _LOGGER.debug("Automation status sensor has value %s", value)
        return value is True

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:home-automation" if self.is_on else "mdi:home-off"


class HeytechLogbookCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor for logbook entry count."""

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
        return "Logbook Entries"

    @property
    def native_value(self) -> int | None:
        """Return the logbook entry count."""
        value = self.coordinator.data.get("logbook_count")
        _LOGGER.debug("Logbook count sensor has value %s", value)
        return int(value) if value is not None else 0

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:book-open-variant"

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "entries"


class HeytechSystemInfoSensor(CoordinatorEntity, SensorEntity):
    """Sensor for system information (model, firmware, device number)."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, info_type: str, unique_id: str
    ) -> None:
        """Initialize the sensor with the coordinator and info type."""
        super().__init__(coordinator)
        self._info_type = info_type
        self._attr_unique_id = unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        name_map = {
            "model": "Model",
            "firmware": "Firmware Version",
            "device_number": "Device Number",
        }
        return name_map.get(self._info_type, self._info_type.capitalize())

    @property
    def native_value(self) -> str | None:
        """Return the system info value."""
        system_info = self.coordinator.data.get("system_info", {})
        value = system_info.get(self._info_type)
        _LOGGER.debug("System info sensor %s has value %s", self._info_type, value)
        return value or "Unknown"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        icon_map = {
            "model": "mdi:chip",
            "firmware": "mdi:package-variant",
            "device_number": "mdi:identifier",
        }
        return icon_map.get(self._info_type, "mdi:information")


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
