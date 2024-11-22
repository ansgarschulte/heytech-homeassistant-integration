"""Constants for heytech."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "heytech"
CONF_PIN = "pin"
CONF_SHUTTERS = "shutters"
# Add a constant for the max shutters setting
CONF_MAX_AUTO_SHUTTERS = "max_auto_shutters"
DEFAULT_MAX_AUTO_SHUTTERS = 10
