# __init__.py
import asyncio
from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PIN, Platform

from .api import HeytechApiClient, IntegrationHeytechApiClientCommunicationError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heytech from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    data = {**entry.data, **entry.options}
    host = data.get(CONF_HOST)
    try:
        port = int(data.get(CONF_PORT, 1002))  # Default to 1002 if not set
    except ValueError:
        _LOGGER.error("Invalid port value: %s. Port must be an integer.", data.get(CONF_PORT))
        raise ConfigEntryNotReady("Invalid port configuration.")
    pin = data.get(CONF_PIN, "")

    # Create API client instance
    api_client = HeytechApiClient(host=host, port=port, pin=pin)
    hass.data[DOMAIN][entry.entry_id]["api_client"] = api_client

    # Test connection to ensure the Heytech device is reachable
    try:
        await api_client.connect()
        _LOGGER.info("Successfully connected to Heytech device at %s:%s", host, port)
    except IntegrationHeytechApiClientCommunicationError as e:
        _LOGGER.error("Failed to connect to Heytech device at %s:%s - %s", host, port, e)
        raise ConfigEntryNotReady from e  # Signal to Home Assistant to retry setup

    # Initialize the DataUpdateCoordinator for periodic updates

    async def async_update_data():
        """Fetch data from the Heytech API."""
        try:
            # Ensure that shutters have been discovered
            if not api_client.shutters:
                _LOGGER.debug("No shutters discovered yet. Sending 'smn' command.")
                await api_client.add_shutter_command("smn", [])

            shutter_positions = await api_client.async_get_data()
            if not shutter_positions:
                raise UpdateFailed("Received empty shutter positions.")
            return shutter_positions
        except IntegrationHeytechApiClientCommunicationError as e:
            raise UpdateFailed(f"Error fetching data: {e}") from e

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Heytech Shutters",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),  # Adjust as needed
    )

    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    # Perform the first refresh
    try:
        await coordinator.async_refresh()
    except UpdateFailed as e:
        _LOGGER.error("Initial data fetch failed: %s", e)
        raise ConfigEntryNotReady from e

    # Forward setup to the configured platforms (e.g., cover)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as e:
        _LOGGER.error("Failed to forward entry setup to platforms: %s", e)
        return False

    # Register unload handler to disconnect properly
    entry.async_on_unload(lambda: asyncio.create_task(async_disconnect(hass, entry)))

    _LOGGER.info("Heytech integration setup successfully for entry %s", entry.entry_id)
    return True

async def async_disconnect(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Disconnect the Heytech API client."""
    try:
        api_client: HeytechApiClient = hass.data[DOMAIN][entry.entry_id]["api_client"]
        await api_client.stop_listening()
        _LOGGER.info("Heytech API client disconnected.")
    except Exception as e:
        _LOGGER.error("Error during disconnect: %s", e)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_disconnect(hass, entry)
        hass.data[DOMAIN].pop(entry.entry_id)

        _LOGGER.info("Heytech integration entry %s unloaded successfully", entry.entry_id)
    else:
        _LOGGER.warning("Heytech integration entry %s failed to unload", entry.entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)