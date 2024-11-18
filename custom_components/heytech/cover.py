import logging

from homeassistant.components.cover import CoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeytechDataUpdateCoordinator
from .const import CONF_SHUTTERS
from .data import IntegrationHeytechConfigEntry

_LOGGER = logging.getLogger(__name__)


class HeytechCover(CoverEntity):
    def __init__(self, name: str, channels: list, coordinator: HeytechDataUpdateCoordinator):
        self.coordinator = coordinator
        self._name = name
        self._channels = channels
        self._is_closed = True  # Assuming shutters start closed by default

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    async def async_open_cover(self, **kwargs):
        _LOGGER.info(f"Opening {self._name} on channels {self._channels}")
        await self._send_command("open")
        self._is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        _LOGGER.info(f"Closing {self._name} on channels {self._channels}")
        await self._send_command("close")
        self._is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        _LOGGER.info(f"Stopping {self._name} on channels {self._channels}")
        await self._send_command("stop")
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs) -> None:
        _LOGGER.info(f"Setting position of {self._name} to {kwargs['position']}%")
        if kwargs["position"] == 100:
            command = "open"
        elif kwargs["position"] == 0:
            command = "close"
        else:
            command = kwargs["position"]
        await self._send_command(command)

    async def _send_command(self, action):
        # Add commands to the queue
        await self.coordinator.config_entry.runtime_data.client.add_shutter_command(action, channels=self._channels)


#
# async def async_setup_platform(
#         hass: HomeAssistant, config: ConfigType, async_add_entities: AddEntitiesCallback, discovery_info=None
# ):
#     """Set up Heytech covers from configuration.yaml."""
#     if discovery_info is None:
#         return
#
#     _LOGGER.info(f"Setting up Heytech covers for platform {discovery_info}")
#
#     data = hass.data[DOMAIN]
#     host = data["host"]
#     port = data["port"]
#     pin = data.get("pin", "")
#     # shutters = data["shutters"]
#
#     covers = []
#     for name, channels in shutters.items():
#         # Parse channels as a list of integers
#         channel_list = [int(channel) for channel in channels.split(",")]
#         # covers.append(HeytechCover(name, channel_list))
#
#     async_add_entities(covers)


async def async_setup_entry(
        hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
        entry: IntegrationHeytechConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    logger = logging.getLogger(__name__)
    logger.info(f"Setting up Heytech covers for entry {entry.entry_id}")
    data = entry.data
    # host = data[CONF_HOST]
    # port = data[CONF_PORT]
    # pin = data.get(CONF_PIN, "")
    shutters = data[CONF_SHUTTERS]
    # shutters = entry.runtime_data.client.get_shutters()
    covers = []
    for name, channels in shutters.items():
        # Parse channels as a list of integers
        channel_list = [int(channel) for channel in channels.split(",")]
        covers.append(HeytechCover(name, channel_list, entry.runtime_data.coordinator))

    async_add_entities(covers)
