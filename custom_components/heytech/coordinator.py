# coordinator.py
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER
from .api import HeytechApiClient

_LOGGER = logging.getLogger(__name__)

class HeytechDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Heytech API."""

    def __init__(
            self,
            hass: HomeAssistant,
            api_client: HeytechApiClient,
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),  # Adjust as needed
        )
        self.api_client = api_client
        self.shutter_positions: Dict[int, int] = {}

    async def _async_update_data(self) -> Dict[int, int]:
        """Fetch data from the Heytech API."""
        try:
            LOGGER.debug("Coordinator: Fetching shutter positions.")
            positions = await self.api_client.async_get_shutter_positions()
            LOGGER.debug("Coordinator: Received shutter positions: %s", positions)
            if not positions:
                raise UpdateFailed("Failed to retrieve shutter positions.")
            self.shutter_positions = positions
            return positions
        except Exception as exception:
            message = f"Error fetching shutter positions: {exception}"
            LOGGER.error(message)
            raise UpdateFailed(message) from exception