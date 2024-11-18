"""
Custom integration to integrate heytech with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/heytech
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from homeassistant.loader import async_get_loaded_integration

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


#
# # Define configuration schema
# CONFIG_SCHEMA = vol.Schema(
#     {
#         DOMAIN: vol.Schema(
#             {
#                 vol.Required(CONF_HOST): cv.string,
#                 vol.Required(CONF_PORT): cv.port,
#                 vol.Required(CONF_PIN): cv.string,
#                 vol.Required(CONF_SHUTTERS): {cv.string: cv.string}
#             }
#         )
#     },
#     extra=vol.ALLOW_EXTRA,
# )


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = HeytechDataUpdateCoordinator(
        hass=hass,
    )
    entry.runtime_data = IntegrationHeytechData(
        client=HeytechApiClient(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            pin=entry.data[CONF_PIN],
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

#
# async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
#     """Set up the heytech component."""
#     conf = config[DOMAIN]
#     host = conf[CONF_HOST]
#     port = conf[CONF_PORT]
#     pin = conf[CONF_PIN]
#     shutters = conf[CONF_SHUTTERS]
#
#     # Load the cover platform and pass along the configuration
#     hass.data[DOMAIN] = {
#         "host": host,
#         "port": port,
#         "pin": pin,
#         "shutters": shutters,
#     }
#
#     hass.async_create_task(
#         async_load_platform(hass, "cover", DOMAIN, {}, config)
#     )
#     return True
