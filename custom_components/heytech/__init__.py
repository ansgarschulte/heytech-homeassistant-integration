"""
Custom integration to integrate heytech with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/heytech
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from homeassistant.loader import async_get_loaded_integration
from homeassistant.setup import async_get_loaded_integrations

from .api import HeytechApiClient
from .const import DOMAIN, CONF_PIN, CONF_SHUTTERS
from .coordinator import HeytechDataUpdateCoordinator
from .data import IntegrationHeytechData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationHeytechConfigEntry

PLATFORMS: list[Platform] = [
    Platform.COVER,
]
_LOGGER = logging.getLogger(__name__)

# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> bool:
    try:
        """Set up Heytech from a config entry."""
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = {}

        data = {**entry.data, **entry.options}
        host = data[CONF_HOST]
        port = data[CONF_PORT]
        pin = data.get(CONF_PIN, "")


        # Create API client instance with updated shutters
        api_client = HeytechApiClient(host=host, port=port, pin=pin)
        hass.data[DOMAIN][entry.entry_id]["api_client"] = api_client

        heytech_coordinator = HeytechDataUpdateCoordinator(
            hass=hass,
            api_client=api_client,
        )
        hass.data[DOMAIN][entry.entry_id]["coordinator"] = heytech_coordinator
        entry.runtime_data = IntegrationHeytechData(
            client=api_client,
            integration=async_get_loaded_integration(hass, entry.domain),
            coordinator=heytech_coordinator,
        )

        # Store runtime data in hass.data
        hass.data[DOMAIN][entry.entry_id]["runtime_data"] = entry.runtime_data

        # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
        await heytech_coordinator.async_config_entry_first_refresh()

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

        return True
    except Exception as e:
        _LOGGER.error(f"Error setting up entry: {e}")
        return False

async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug(f"Options updated for entry: {config_entry.entry_id}")
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_unload_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

