# coordinator.py
"""Data coordinator for the Heytech integration."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeytechApiClient
from .const import DOMAIN, LOGGER

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
            update_interval=timedelta(seconds=60),  # Adjust as needed
        )
        self.api_client = api_client
        self.shutter_positions: dict[int, int] = {}

    async def _async_update_data(self) -> dict[int, int]:
        """Fetch data from the Heytech API."""
        try:
            positions = await self.api_client.async_get_shutter_positions()
            if not positions:
                await self._handle_no_positions()
            else:
                self.shutter_positions = positions
                return positions
        except Exception as exception:
            error_message = f"Error fetching shutter positions: {exception}"
            LOGGER.error(error_message)
            raise UpdateFailed(error_message) from exception

    async def _handle_no_positions(self) -> None:
        """Handle the case when no shutter positions are received."""
        error_message = "Failed to retrieve shutter positions."
        raise UpdateFailed(error_message)
