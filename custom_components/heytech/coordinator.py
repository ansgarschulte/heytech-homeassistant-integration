"""DataUpdateCoordinator for heytech."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeytechApiClient
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationHeytechConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class HeytechDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: IntegrationHeytechConfigEntry

    def __init__(
            self,
            hass: HomeAssistant,
            api_client: HeytechApiClient,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.api_client = api_client
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            # return await self.api_client.async_get_data()
            return None
        except Exception as exception:
            raise UpdateFailed() from exception