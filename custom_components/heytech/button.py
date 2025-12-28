"""Button platform for Heytech integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api import HeytechApiClient
    from .coordinator import HeytechDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heytech button entities."""
    api_client: HeytechApiClient = hass.data[DOMAIN][entry.entry_id]["api_client"]
    coordinator: HeytechDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Create button entity for time synchronization
    async_add_entities([HeytechSyncTimeButton(coordinator, api_client, entry.entry_id)])


class HeytechSyncTimeButton(CoordinatorEntity, ButtonEntity):
    """Button entity for synchronizing time with Heytech controller."""

    def __init__(
        self,
        coordinator: HeytechDataUpdateCoordinator,
        api_client: HeytechApiClient,
        entry_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._api_client = api_client
        self._attr_name = "Synchronize Time"
        self._attr_unique_id = f"{entry_id}_sync_time_button"
        self._attr_icon = "mdi:clock-sync"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Sync Time button pressed")
        try:
            await self._api_client.async_sync_time()
            _LOGGER.info("Time synchronized successfully")
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to sync time: %s", e)
