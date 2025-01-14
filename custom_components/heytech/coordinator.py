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
            update_interval=timedelta(seconds=30),  # Adjust as needed
            always_update=False,
        )
        self.api_client = api_client
        self.shutter_positions: dict[int, int] = {}
        self.climate_data: dict[str, str] = {}

    async def _async_setup(self) -> None:
        """
        Set up the coordinator.

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        await self.api_client.async_read_heytech_data()
        positions = await self.api_client.async_wait_for_shutter_positions()
        if not positions:
            _LOGGER.warning("No shutter positions received.")
            await self._handle_no_data()
        climate_data = await self.api_client.async_get_climate_data()
        if not climate_data:
            _LOGGER.warning("No climate data received.")
            await self._handle_no_data()

    async def _async_update_data(self) -> dict[str, dict[any, any]]:
        """Fetch data from the Heytech API."""
        result = {}
        try:
            positions = self.api_client.get_shutter_positions()
            climate_data = self.api_client.get_climate_data()
            if not positions:
                _LOGGER.warning("No shutter positions received.")
            if not climate_data:
                _LOGGER.warning("No climate data received.")
            if not positions and not climate_data:
                await self._handle_no_data()
            if climate_data:
                self.climate_data = climate_data
                result["climate_data"] = climate_data
            if positions:
                self.shutter_positions = positions
                result["shutter_positions"] = positions
        except Exception as exception:
            error_message = f"Error fetching shutter positions: {exception}"
            LOGGER.error(error_message)
            raise UpdateFailed(error_message) from exception
        else:
            return result

    async def _handle_no_data(self) -> None:
        """Handle the case when no shutter positions are received."""
        error_message = "Failed to retrieve shutter positions and climate data."
        raise UpdateFailed(error_message)
