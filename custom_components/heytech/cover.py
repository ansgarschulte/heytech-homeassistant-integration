"""
Heytech Cover Integration for Home Assistant.

This module provides support for Heytech covers within Home Assistant,
allowing users to control their Heytech shutters via the Home Assistant interface.
"""

import asyncio
import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature, CoverDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HeytechApiClient
from .api import IntegrationHeytechApiClientError
from .const import (
    CONF_MAX_AUTO_SHUTTERS,
    CONF_SHUTTERS,
    DEFAULT_MAX_AUTO_SHUTTERS,
    DOMAIN,
)
from .coordinator import HeytechDataUpdateCoordinator
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
    coordinator: HeytechDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Fetch dynamic shutters from the API
    await api_client.async_read_heytech_data()
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

        unique_id = f"{entry.entry_id}_{name}_{'_'.join(map(str, channels))}"
        current_unique_ids.add(unique_id)
        _LOGGER.info("Adding cover '%s' with channels %s", name, channel_list)
        covers.append(
            HeytechCover(name, channel_list, api_client, unique_id, coordinator)
        )

    # Add new entities
    async_add_entities(covers)

    # Remove entities and devices that are no longer in the configuration
    await _async_cleanup_entities_and_devices(hass, entry, current_unique_ids)
    await coordinator.async_refresh()


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


class HeytechCover(CoordinatorEntity[HeytechDataUpdateCoordinator], CoverEntity):
    """Representation of a Heytech cover."""

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
        coordinator: HeytechDataUpdateCoordinator,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)
        if "markise" in name.lower() or "awning" in name.lower():
            self._is_awning = True
        else:
            self._is_awning = False
        self._api_client = api_client
        self._unique_id = unique_id
        self._name = name
        self._channels = channels
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._prev_position: int | None = None  # Current position
        self._position: int | None = None  # Current position
        self._is_opening: bool = False
        self._is_closing: bool = False
        if self._is_awning:
            self._attr_device_class = CoverDeviceClass.AWNING
        else:
            self._attr_device_class = CoverDeviceClass.SHUTTER

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this cover."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "Heytech",
            "model": "Shutter",
        }

    @property
    def is_opening(self) -> bool:
        """Return whether the cover is opening or not."""
        return self._is_opening

    @property
    def is_closing(self) -> bool:
        """Return whether the cover is closing or not."""
        return self._is_closing

    @property
    def is_closed(self) -> bool:
        """Return whether the cover is closed based on current position."""
        if self._position is None:
            _LOGGER.debug(
                "Cover '%s' position is unknown. Assuming not closed.", self._name
            )
            return False  # Unknown state
        return self._position == MIN_POSITION

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self._position

    async def async_open_cover(self, **_kwargs: Any) -> None:
        """Open the cover."""
        _LOGGER.info("Opening %s on channels %s", self._name, self._channels)
        if self._is_awning:
            await self.async_set_cover_position(position=MIN_POSITION)
        else:
            await self.async_set_cover_position(position=MAX_POSITION)
        self._is_opening = True
        self.async_write_ha_state()

    async def async_close_cover(self, **_kwargs: Any) -> None:
        """Close the cover."""
        _LOGGER.info("Closing %s on channels %s", self._name, self._channels)
        if self._is_awning:
            await self.async_set_cover_position(position=MAX_POSITION)
        else:
            await self.async_set_cover_position(position=MIN_POSITION)
        self._is_closing = True
        self.async_write_ha_state()

    async def _force_position_refresh_later(self) -> None:
        for _i in range(20):
            await asyncio.sleep(1)
            await self._api_client.async_read_shutters_positions()
            await self.coordinator.async_refresh()
        self._is_opening = False
        self._is_closing = False
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            _LOGGER.error("Position not provided for setting cover position.")
            return
        _LOGGER.info("Setting position of %s to %s%%", self._name, position)
        try:
            await self._api_client.add_command(f"{position}", self._channels)
            if self._position is not None:
                if position > self._position:
                    self._is_opening = True
                    self._is_closing = False
                elif position < self._position:
                    self._is_opening = False
                    self._is_closing = True
            self._prev_position = self._position
            self._position = position
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
            self.hass.async_create_task(
                self._force_position_refresh_later(),
                "force_position_refresh_later_for_" + self._name,
            )
        except IntegrationHeytechApiClientError:
            _LOGGER.exception("Failed to set position for %s", self._name)
            return
        # The coordinator will update the position on next update

    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        _LOGGER.info("Stopping %s on channels %s", self._name, self._channels)
        try:
            await self._api_client.add_command("stop", self._channels)
            self._is_opening = False
            self._is_closing = False
            self.async_write_ha_state()
        except IntegrationHeytechApiClientError:
            _LOGGER.exception("Failed to stop %s", self._name)

    def _handle_coordinator_update(self) -> None:
        """Update the cover's state from the coordinator."""
        self._prev_position = self._position
        positions = self.coordinator.data.get("shutter_positions", {})
        if not self._channels:
            self._position = None
        else:
            # Collect positions for all associated channels
            channel_positions = [
                positions.get(channel, None) for channel in self._channels
            ]
            # Filter out None values
            channel_positions = [pos for pos in channel_positions if pos is not None]
            if channel_positions:
                # If multiple channels, decide how to represent the position
                # Here, we take the average position
                self._position = sum(channel_positions) // len(channel_positions)
            else:
                self._position = None

        if self._position is not None and self._prev_position is not None:
            if self._position == self._prev_position:
                self._is_opening = False
                self._is_closing = False
        else:
            self._is_opening = False
            self._is_closing = False
        self.async_write_ha_state()


class InvalidChannelFormatError(TypeError):
    """Exception raised for invalid channel format."""

    def __init__(self, name: str, channels: Any) -> None:
        """Initialize the InvalidChannelFormatError."""
        super().__init__(f"Invalid channel format for '{name}': {channels}")
