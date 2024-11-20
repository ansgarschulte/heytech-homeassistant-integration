"""
DataUpdateCoordinator for Heytech.

This module defines the HeytechDataUpdateCoordinator class, which manages data updates
from the Heytech API for Home Assistant integrations.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import HeytechApiClient
    from .data import IntegrationHeytechConfigEntry


class HeytechDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Heytech API."""

    config_entry: IntegrationHeytechConfigEntry

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
            update_interval=timedelta(hours=1),
        )
        self.api_client = api_client

    async def _async_update_data(self) -> None:
        """Fetch data from the Heytech API."""
        try:
            # Placeholder for actual data fetching logic
            return
        except Exception as exception:
            # EM102: Assign exception message to variable before raising
            message = str(exception)
            # TRY003: Avoid specifying long messages outside the exception class
            raise UpdateFailed(message) from exception
