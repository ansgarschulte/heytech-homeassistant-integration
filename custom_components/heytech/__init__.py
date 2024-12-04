"""
Custom integration to integrate Heytech with Home Assistant.

For more details about this integration, please refer to:
https://github.com/ansgarschulte/heytech-homeassistant-integration
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .api import HeytechApiClient
from .const import CONF_PIN, DOMAIN
from .coordinator import HeytechDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.COVER]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Heytech from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(
        entry.entry_id, {}
    )  # Use setdefault instead of overwriting

    data = {**entry.data, **entry.options}
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    pin = data.get(CONF_PIN, "")

    # Retrieve existing API client instance if available
    api_client = hass.data[DOMAIN][entry.entry_id].get("api_client")
    if api_client:
        # Check if connection parameters have changed
        _LOGGER.debug("ToDo: Checking if connection parameters have changed.")
        # Implement logic to update the API client if needed
    else:
        _LOGGER.debug("Creating Heytech API client.")
        api_client = HeytechApiClient(host=host, port=port, pin=pin)
        hass.data[DOMAIN][entry.entry_id]["api_client"] = api_client

    # Initialize the DataUpdateCoordinator for periodic updates
    heytech_coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
    if not heytech_coordinator:
        _LOGGER.debug("Creating Heytech DataUpdateCoordinator.")
        heytech_coordinator = HeytechDataUpdateCoordinator(
            hass=hass,
            api_client=api_client,
        )
        hass.data[DOMAIN][entry.entry_id]["coordinator"] = heytech_coordinator
    else:
        # Update the coordinator's api_client if it has changed
        heytech_coordinator.api_client = api_client

    # Perform the first refresh to populate initial data
    _LOGGER.debug("Starting first refresh of coordinator.")
    try:
        await heytech_coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("First refresh of coordinator completed successfully.")
    except ConfigEntryNotReady:
        _LOGGER.exception(
            "Initial data fetch failed. Marking config entry as not ready."
        )
        raise

    # Forward setup to the configured platforms (e.g., cover)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        _LOGGER.exception("Failed to forward entry setup to platforms")
        return False

    # Add an update listener to handle option changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Heytech integration setup successfully for entry %s", entry.entry_id)
    return True


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Retrieve the API client
        api_client = hass.data[DOMAIN][entry.entry_id].get("api_client")
        if api_client:
            try:
                await api_client.stop()
                _LOGGER.debug("API client stopped successfully.")
            except Exception:
                _LOGGER.exception("Error stopping API client")

        # Remove the entry from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

        _LOGGER.info(
            "Heytech integration entry %s unloaded successfully", entry.entry_id
        )
    else:
        _LOGGER.warning("Heytech integration entry %s failed to unload", entry.entry_id)
    return unload_ok
