"""Custom types for heytech."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import HeytechApiClient
    from .coordinator import HeytechDataUpdateCoordinator

type IntegrationHeytechConfigEntry = ConfigEntry[IntegrationHeytechData]


@dataclass
class IntegrationHeytechData:
    """Data for the Heytech integration."""

    client: HeytechApiClient
    coordinator: HeytechDataUpdateCoordinator
    integration: Integration
