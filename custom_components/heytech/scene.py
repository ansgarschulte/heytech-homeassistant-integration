"""
Heytech Scene Integration for Home Assistant.

This module provides support for Heytech scenarios within Home Assistant,
allowing users to activate predefined scenarios on their Heytech controller.
"""

import asyncio
import logging
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeytechApiClient
from .api import IntegrationHeytechApiClientError
from .const import DOMAIN
from .data import IntegrationHeytechConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationHeytechConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heytech scenes based on a config entry."""
    _LOGGER.info("Setting up Heytech scenes for entry %s", entry.entry_id)
    api_client: HeytechApiClient = hass.data[DOMAIN][entry.entry_id]["api_client"]

    # Wait a bit for discovery to complete
    # The coordinator runs async_read_heytech_data() which discovers scenarios
    # This happens in parallel with platform setup, so we need to wait
    await asyncio.sleep(2)  # Give discovery time to complete
    
    # Fetch scenarios from the API
    scenarios = api_client.get_scenarios()
    
    if not scenarios:
        _LOGGER.warning("No scenarios found on Heytech device - will retry discovery")
        # Trigger another discovery attempt
        try:
            await api_client.async_read_heytech_data()
            await asyncio.sleep(1)  # Wait for responses
            scenarios = api_client.get_scenarios()
        except Exception:
            _LOGGER.exception("Failed to discover scenarios")
    
    if not scenarios:
        _LOGGER.warning("Still no scenarios found after retry")
        return

    scenes = []
    for scenario_num, scenario_name in scenarios.items():
        unique_id = f"{entry.entry_id}_scenario_{scenario_num}"
        _LOGGER.info("Adding scene '%s' (number %d)", scenario_name, scenario_num)
        scenes.append(
            HeytechScene(scenario_name, scenario_num, api_client, unique_id)
        )

    async_add_entities(scenes)
    _LOGGER.info("Successfully added %d Heytech scenes", len(scenes))


class HeytechScene(Scene):
    """Representation of a Heytech scene."""

    def __init__(
        self,
        name: str,
        scenario_number: int,
        api_client: HeytechApiClient,
        unique_id: str,
    ) -> None:
        """Initialize the scene."""
        self._api_client = api_client
        self._unique_id = unique_id
        self._name = name
        self._scenario_number = scenario_number
        self._attr_name = name
        self._attr_unique_id = unique_id

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this scene."""
        return {
            "identifiers": {(DOMAIN, f"heytech_scenarios")},
            "name": "Heytech Scenarios",
            "manufacturer": "Heytech",
            "model": "Scenario Controller",
        }

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        _LOGGER.info("Activating scenario '%s' (number %d)", self._name, self._scenario_number)
        try:
            await self._api_client.async_activate_scenario(self._scenario_number)
        except IntegrationHeytechApiClientError:
            _LOGGER.exception("Failed to activate scenario '%s'", self._name)
