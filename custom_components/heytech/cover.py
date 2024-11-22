"""
Heytech Cover Integration for Home Assistant.

This module provides support for Heytech covers within Home Assistant,
allowing users to control their Heytech shutters via the Home Assistant interface.
"""

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeytechApiClient
from .const import (
    CONF_MAX_AUTO_SHUTTERS,
    CONF_SHUTTERS,
    DEFAULT_MAX_AUTO_SHUTTERS,
    DOMAIN,
)
from .data import IntegrationHeytechConfigEntry

_LOGGER = logging.getLogger(__name__)

# Constants for the cover position
ATTR_POSITION = "position"
MAX_POSITION = 100
MIN_POSITION = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationHeytechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heytech covers based on a config entry."""
    _LOGGER.info("Setting up Heytech covers for entry %s", entry.entry_id)
    api_client: HeytechApiClient = hass.data[DOMAIN][entry.entry_id]["api_client"]

    # Fetch dynamic shutters from the API
    await api_client.async_get_data()
    dynamic_shutters = api_client.shutters  # Get parsed shutters from the API

    # Limit the number of dynamic shutters
    max_auto_shutters = int(
        entry.data.get(CONF_MAX_AUTO_SHUTTERS, DEFAULT_MAX_AUTO_SHUTTERS)
    )
    limited_dynamic_shutters = dict(list(dynamic_shutters.items())[:max_auto_shutters])

    # Normalize dynamic shutters to comma-separated channels
    normalized_dynamic_shutters = {
        name: str(details["channel"])
        for name, details in limited_dynamic_shutters.items()
    }

    # Get updated custom-configured shutters from the config entry
    configured_shutters = entry.options.get(
        CONF_SHUTTERS, entry.data.get(CONF_SHUTTERS, {})
    )

    # Merge configured shutters with normalized and limited dynamic shutters
    all_shutters = {**configured_shutters, **normalized_dynamic_shutters}

    covers = []
    current_unique_ids: set[str] = set()

    for name, channels in all_shutters.items():
        try:
            # Ensure channels are parsed into a list of integers
            if isinstance(channels, str):
                channel_list = [int(ch.strip()) for ch in channels.split(",")]
            else:
                raise InvalidChannelFormatError(name, channels)
        except ValueError as exc:
            _LOGGER.warning(
                "Skipping invalid channel configuration for '%s': %s", name, exc
            )
            continue

        unique_id = f"{entry.entry_id}_{name}"
        current_unique_ids.add(unique_id)
        _LOGGER.info("Adding cover '%s' with channels %s", name, channel_list)
        covers.append(HeytechCover(name, channel_list, api_client, unique_id))

    # Add new entities
    async_add_entities(covers)

    # Remove entities and devices that are no longer in the configuration
    await _async_cleanup_entities_and_devices(hass, entry, current_unique_ids)


async def _async_cleanup_entities_and_devices(
    hass: HomeAssistant,
    entry: IntegrationHeytechConfigEntry,
    current_unique_ids: set[str],
) -> None:
    """Remove entities and devices that are no longer in the configuration."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    # Map devices to their associated entities
    device_entities: dict[str, list[er.RegistryEntry]] = {}

    for entity_entry in entries:
        if entity_entry.domain != "cover":
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


class HeytechCover(CoverEntity):
    """Representation of a Heytech cover."""

    _attr_is_closed: bool = True  # Default to fully closed
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        name: str,
        channels: list[int],
        api_client: HeytechApiClient,
        unique_id: str,
    ) -> None:
        """Initialize the cover."""
        self._api_client = api_client
        self._unique_id = unique_id
        self._name = name
        self._channels = channels
        self._attr_name = name
        self._attr_unique_id = unique_id

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this cover."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "Heytech",
            "model": "Shutter",
        }

    async def async_open_cover(self, **_kwargs: Any) -> None:
        """Open the cover."""
        _LOGGER.info("Opening %s on channels %s", self._name, self._channels)
        await self.async_set_cover_position(position=MAX_POSITION)

    async def async_close_cover(self, **_kwargs: Any) -> None:
        """Close the cover."""
        _LOGGER.info("Closing %s on channels %s", self._name, self._channels)
        await self.async_set_cover_position(position=MIN_POSITION)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        _LOGGER.info("Setting position of %s to %s%%", self._name, position)
        self._attr_is_closed = position == MIN_POSITION
        await self._api_client.add_shutter_command(f"{position}", self._channels)
        self.async_write_ha_state()

    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        _LOGGER.info("Stopping %s on channels %s", self._name, self._channels)
        await self._api_client.add_shutter_command("stop", self._channels)
        self.async_write_ha_state()


class InvalidChannelFormatError(TypeError):
    """Exception raised for invalid channel format."""

    def __init__(self, name: str, channels: Any) -> None:
        """Initialize the InvalidChannelFormatError."""
        super().__init__(f"Invalid channel format for '{name}': {channels}")
