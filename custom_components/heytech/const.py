"""Constants for heytech."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "heytech"
CONF_PIN = "pin"
CONF_SHUTTERS = "shutters"
# Add a constant for the max shutters setting
CONF_MAX_AUTO_SHUTTERS = "max_auto_shutters"
DEFAULT_MAX_AUTO_SHUTTERS = 10
# Optional: XT-PICO serial-to-IP adapter management password (Telnet port 23).
# When set, enables automatic binary-mode recovery after power outages by
# restarting the adapter interface, which pulses the DTR line and causes
# the controller to reboot into normal ASCII mode.
CONF_ADAPTER_PASSWORD = "adapter_password"
