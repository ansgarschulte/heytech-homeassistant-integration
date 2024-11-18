import logging

from homeassistant.components.cover import CoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from . import HeytechApiClient
from .const import CONF_SHUTTERS, DOMAIN
from .data import IntegrationHeytechConfigEntry

_LOGGER = logging.getLogger(__name__)


class HeytechCover(CoverEntity):
    def __init__(self, name: str, channels: list, api_client: HeytechApiClient, unique_id: str):
        self._api_client = api_client
        self._unique_id = unique_id
        self._name = name
        self._channels = channels
        self._is_closed = True  # Assuming shutters start closed by default

    @property
    def unique_id(self):
        """Return a unique ID for this cover."""
        return self._unique_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def device_info(self):
        """Return device information about this cover."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            name=self._name,
            manufacturer="Heytech",
            model="Shutter",
        )

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
        await self._api_client.add_shutter_command(action, channels=self._channels)


async def async_setup_entry(
        hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
        entry: IntegrationHeytechConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> bool:

    _LOGGER.info(f"Setting up Heytech covers for entry {entry.entry_id}")
    data = {**entry.data, **entry.options}
    api_client = hass.data[DOMAIN][entry.entry_id]["api_client"]
    shutters = data[CONF_SHUTTERS]
    _LOGGER.debug(f"Shutters: {shutters}")

    registry = async_get_entity_registry(hass)
    entities = [
        entity for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    ]
    existing_entities = {entity.unique_id: entity for entity in entities}
    _LOGGER.debug(f"Existing entities: {existing_entities}")

    # Remove entities that are no longer configured
    # for entity in existing_entities.values():
    #     if entity.unique_id not in [f"{entry.entry_id}_{name}" for name in shutters.keys()]:
    #         registry.async_remove(entity.entity_id)

    # Add or update entities
    covers = []
    for name, channels in shutters.items():
        unique_id = f"{entry.entry_id}_{name}"
        # Check if entity already exists
        if unique_id in existing_entities:
            continue  # Entity already exists, no need to add
        # Parse channels as a list of integers
        channel_list = [int(channel.strip()) for channel in channels.split(",")]
        _LOGGER.info(f"Adding cover {name} with channels {channel_list}")
        covers.append(HeytechCover(name, channel_list, api_client, unique_id))

    if covers:
        async_add_entities(covers, update_before_add=True)

    return True  # Indicate successful setup
