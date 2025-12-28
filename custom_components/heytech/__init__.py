"""
Custom integration to integrate Heytech with Home Assistant.

For more details about this integration, please refer to:
https://github.com/ansgarschulte/heytech-homeassistant-integration
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .api import HeytechApiClient
from .const import CONF_PIN, CONF_SHUTTERS, DOMAIN
from .coordinator import HeytechDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SENSOR, Platform.SCENE, Platform.BUTTON]
_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_READ_LOGBOOK = "read_logbook"
SERVICE_CLEAR_LOGBOOK = "clear_logbook"
SERVICE_CONTROL_GROUP = "control_group"
SERVICE_EXPORT_SHUTTERS = "export_shutters_config"
SERVICE_IMPORT_SHUTTERS = "import_shutters_config"
SERVICE_SYNC_TIME = "sync_time"

SCHEMA_READ_LOGBOOK = vol.Schema(
    {
        vol.Optional("max_entries", default=50): cv.positive_int,
    }
)

SCHEMA_CLEAR_LOGBOOK = vol.Schema({})

SCHEMA_CONTROL_GROUP = vol.Schema(
    {
        vol.Required("group_number"): cv.positive_int,
        vol.Required("action"): cv.string,
    }
)

SCHEMA_EXPORT_SHUTTERS = vol.Schema(
    {
        vol.Optional("filename", default="heytech_shutters_backup"): cv.string,
    }
)

SCHEMA_IMPORT_SHUTTERS = vol.Schema(
    {
        vol.Required("config_data"): cv.string,
    }
)

SCHEMA_SYNC_TIME = vol.Schema({})


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
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to forward entry setup to platforms")
        return False

    # Add an update listener to handle option changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services
    await async_setup_services(hass, api_client)

    _LOGGER.info("Heytech integration setup successfully for entry %s", entry.entry_id)
    return True


async def async_setup_services(
    hass: HomeAssistant, api_client: HeytechApiClient
) -> None:
    """Set up services for Heytech integration."""

    async def handle_read_logbook(call: ServiceCall) -> None:
        """Handle the read_logbook service call."""
        max_entries = call.data.get("max_entries", 50)
        _LOGGER.info("Reading logbook with max %d entries", max_entries)
        entries = await api_client.async_read_logbook(max_entries)
        _LOGGER.info("Read %d logbook entries", len(entries))
        # Optionally fire an event with the logbook data
        hass.bus.async_fire(
            "heytech_logbook_read",
            {"entries": entries, "count": len(entries)},
        )

    async def handle_clear_logbook(call: ServiceCall) -> None:
        """Handle the clear_logbook service call."""
        _LOGGER.info("Clearing logbook")
        await api_client.async_clear_logbook()

    async def handle_control_group(call: ServiceCall) -> None:
        """Handle the control_group service call."""
        group_number = call.data["group_number"]
        action = call.data["action"]
        _LOGGER.info("Controlling group %d with action %s", group_number, action)
        await api_client.async_control_group(group_number, action)

    async def handle_export_shutters(call: ServiceCall) -> None:
        """Handle the export_shutters_config service call."""
        filename = call.data.get("filename", "heytech_shutters_backup")
        _LOGGER.info("Exporting shutters configuration to %s", filename)
        
        # Get the config entry for this domain
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.error("No Heytech config entries found")
            return
        
        entry = entries[0]  # Get first entry
        shutters = entry.options.get(CONF_SHUTTERS, entry.data.get(CONF_SHUTTERS, {}))
        
        # Create export data
        export_data = {
            "version": "1.0",
            "exported_at": hass.helpers.template.now().isoformat(),
            "shutters": shutters,
        }
        
        # Save to file in Home Assistant's config directory
        import os
        filepath = os.path.join(hass.config.path(), f"{filename}.json")
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            _LOGGER.info("Exported %d custom shutters to %s", len(shutters), filepath)
            
            # Show persistent notification with export location
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": (
                        f"Configuration exported successfully!\n\n"
                        f"**Location:** `{filepath}`\n"
                        f"**Shutters:** {len(shutters)}\n\n"
                        f"You can download it via File Editor, SSH, or Samba."
                    ),
                    "title": "Heytech Configuration Exported",
                    "notification_id": "heytech_export_success",
                },
            )
            
            # Fire success event
            hass.bus.async_fire(
                "heytech_config_exported",
                {
                    "filename": f"{filename}.json",
                    "filepath": filepath,
                    "shutters_count": len(shutters),
                },
            )
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to export configuration: %s", e)
            
            # Show error notification
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": (
                        f"Failed to export configuration!\n\n"
                        f"**Error:** {e}\n\n"
                        f"Check the logs for more details."
                    ),
                    "title": "Heytech Export Failed",
                    "notification_id": "heytech_export_failed",
                },
            )
            
            hass.bus.async_fire(
                "heytech_config_export_failed",
                {"error": str(e)},
            )

    async def handle_import_shutters(call: ServiceCall) -> None:
        """Handle the import_shutters_config service call."""
        config_data = call.data["config_data"]
        _LOGGER.info("Importing shutters configuration")
        
        try:
            # Parse JSON data
            import_data = json.loads(config_data)
            
            if "shutters" not in import_data:
                _LOGGER.error("Invalid config data: missing 'shutters' key")
                hass.bus.async_fire(
                    "heytech_config_import_failed",
                    {"error": "Invalid config data: missing 'shutters' key"},
                )
                return
            
            shutters = import_data["shutters"]
            
            # Get the config entry
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                _LOGGER.error("No Heytech config entries found")
                return
            
            entry = entries[0]
            
            # Update the config entry with imported shutters
            new_options = {**entry.options, CONF_SHUTTERS: shutters}
            hass.config_entries.async_update_entry(entry, options=new_options)
            
            # Fire success event
            hass.bus.async_fire(
                "heytech_config_imported",
                {"shutters_count": len(shutters)},
            )
            _LOGGER.info("Imported %d custom shutters successfully", len(shutters))
            
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse JSON: %s", e)
            hass.bus.async_fire(
                "heytech_config_import_failed",
                {"error": f"Invalid JSON: {e}"},
            )

    async def handle_sync_time(call: ServiceCall) -> None:
        """Handle the sync_time service call."""
        _LOGGER.info("Synchronizing time with Heytech controller")
        try:
            await api_client.async_sync_time()
            _LOGGER.info("Time synchronized successfully")
            
            # Show success notification
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": "Time synchronized successfully with Heytech controller.",
                    "title": "Heytech Time Sync",
                    "notification_id": "heytech_time_sync_success",
                },
            )
            
            hass.bus.async_fire("heytech_time_synced")
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to sync time: %s", e)
            
            # Show error notification
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Failed to sync time: {e}",
                    "title": "Heytech Time Sync Failed",
                    "notification_id": "heytech_time_sync_failed",
                },
            )
            
            hass.bus.async_fire(
                "heytech_time_sync_failed",
                {"error": str(e)},
            )

    # Register services only once
    if not hass.services.has_service(DOMAIN, SERVICE_READ_LOGBOOK):
        hass.services.async_register(
            DOMAIN, SERVICE_READ_LOGBOOK, handle_read_logbook, schema=SCHEMA_READ_LOGBOOK
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_LOGBOOK):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_LOGBOOK,
            handle_clear_logbook,
            schema=SCHEMA_CLEAR_LOGBOOK,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_CONTROL_GROUP):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CONTROL_GROUP,
            handle_control_group,
            schema=SCHEMA_CONTROL_GROUP,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_EXPORT_SHUTTERS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_EXPORT_SHUTTERS,
            handle_export_shutters,
            schema=SCHEMA_EXPORT_SHUTTERS,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_IMPORT_SHUTTERS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_IMPORT_SHUTTERS,
            handle_import_shutters,
            schema=SCHEMA_IMPORT_SHUTTERS,
        )
    
    if not hass.services.has_service(DOMAIN, SERVICE_SYNC_TIME):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SYNC_TIME,
            handle_sync_time,
            schema=SCHEMA_SYNC_TIME,
        )


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
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error stopping API client")

        # Remove the entry from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

        # Unregister services if no other entries exist
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_READ_LOGBOOK)
            hass.services.async_remove(DOMAIN, SERVICE_CLEAR_LOGBOOK)
            hass.services.async_remove(DOMAIN, SERVICE_CONTROL_GROUP)
            hass.services.async_remove(DOMAIN, SERVICE_EXPORT_SHUTTERS)
            hass.services.async_remove(DOMAIN, SERVICE_IMPORT_SHUTTERS)

        _LOGGER.info(
            "Heytech integration entry %s unloaded successfully", entry.entry_id
        )
    else:
        _LOGGER.warning("Heytech integration entry %s failed to unload", entry.entry_id)
    return unload_ok
