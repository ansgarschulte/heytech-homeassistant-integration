"""
Custom integration to integrate heytech with Home Assistant.

For more details about this integration, please refer to
https://github.com/ansgarschulte/heytech-homeassistant-integration
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from homeassistant.loader import async_get_loaded_integration

from .api import HeytechApiClient
from .const import DOMAIN, CONF_PIN
from .coordinator import HeytechDataUpdateCoordinator
from .data import IntegrationHeytechData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationHeytechConfigEntry

PLATFORMS: list[Platform] = [
    Platform.COVER,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> bool:
    """Set up Heytech from a config entry."""
    try:
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = {}

        data = {**entry.data, **entry.options}
        host = data[CONF_HOST]
        port = data[CONF_PORT]
        pin = data.get(CONF_PIN, "")

        # Create API client instance
        api_client = HeytechApiClient(host=host, port=port, pin=pin)
        hass.data[DOMAIN][entry.entry_id]["api_client"] = api_client

        heytech_coordinator = HeytechDataUpdateCoordinator(
            hass=hass,
            api_client=api_client,
        )
        hass.data[DOMAIN][entry.entry_id]["coordinator"] = heytech_coordinator
        entry.runtime_data = IntegrationHeytechData(
            client=api_client,
            integration=async_get_loaded_integration(hass, entry.domain),  # Removed await here
            coordinator=heytech_coordinator,
        )

        # Store runtime data in hass.data
        hass.data[DOMAIN][entry.entry_id]["runtime_data"] = entry.runtime_data

        # First data refresh
        await heytech_coordinator.async_config_entry_first_refresh()

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Add the update listener back
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

        return True
    except Exception as e:
        _LOGGER.error(f"Error setting up entry: {e}")
        return False


async def async_reload_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok