import logging

from homeassistant.components.cover import CoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeytechApiClient
from .const import CONF_SHUTTERS, DOMAIN
from .data import IntegrationHeytechConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: IntegrationHeytechConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heytech covers based on a config entry."""
    _LOGGER.info(f"Setting up Heytech covers for entry {entry.entry_id}")
    data = {**entry.data, **entry.options}
    api_client = hass.data[DOMAIN][entry.entry_id]["api_client"]

    shutters = data.get(CONF_SHUTTERS, {})
    covers = []
    for name, channels in shutters.items():
        unique_id = f"{entry.entry_id}_{name}"
        channel_list = [int(channel.strip()) for channel in channels.split(",")]
        covers.append(HeytechCover(name, channel_list, api_client, unique_id))

    async_add_entities(covers)


class HeytechCover(CoverEntity):
    """Representation of a Heytech cover."""

    def __init__(
            self, name: str, channels: list, api_client: HeytechApiClient, unique_id: str
    ):
        """Initialize the cover."""
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
        """Return the name of the cover."""
        return self._name

    @property
    def device_info(self):
        """Return device information about this cover."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self._name,
            "manufacturer": "Heytech",
            "model": "Shutter",
        }

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self._is_closed

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.info(f"Opening {self._name} on channels {self._channels}")
        await self._send_command("open")
        self._is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        _LOGGER.info(f"Closing {self._name} on channels {self._channels}")
        await self._send_command("close")
        self._is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        _LOGGER.info(f"Stopping {self._name} on channels {self._channels}")
        await self._send_command("stop")
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs) -> None:
        """Set the cover to a specific position."""
        _LOGGER.info(f"Setting position of {self._name} to {kwargs['position']}%")
        if kwargs["position"] == 100:
            command = "open"
        elif kwargs["position"] == 0:
            command = "close"
        else:
            command = kwargs["position"]
        await self._send_command(command)

    async def _send_command(self, action):
        """Send a command to the cover."""
        await self._api_client.add_shutter_command(action, channels=self._channels)