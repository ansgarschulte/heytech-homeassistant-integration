"""Adds config flow for Heytech."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.helpers import selector

from . import HeytechApiClient
from .api import IntegrationHeytechApiClientCommunicationError, IntegrationHeytechApiClientError
from .const import DOMAIN, LOGGER, CONF_PIN, CONF_SHUTTERS


class HeytechFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Heytech."""

    VERSION = 1

    def __init__(self):
        self._host = None
        self._port = None
        self._pin = None
        self._shutters = {}
        self._shutter_name = None
        self._shutter_channels = None

    async def async_step_user(
            self,
            user_input: dict | None = None,
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._pin = user_input.get(CONF_PIN, "")

            # Validate connection
            try:
                await self._test_credentials(
                    host=self._host,
                    port=self._port,
                    pin=self._pin,
                )
            except IntegrationHeytechApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except IntegrationHeytechApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                # Proceed to shutters configuration step
                return await self.async_step_shutter()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=(user_input or {}).get(CONF_HOST, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        CONF_PORT,
                        default=(user_input or {}).get(CONF_PORT, 1002),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=65535,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_PIN,
                        default=(user_input or {}).get(CONF_PIN, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def async_step_shutter(
            self,
            user_input: dict | None = None,
    ) -> data_entry_flow.FlowResult:
        """Step to add shutters."""
        _errors = {}
        if user_input is not None:
            self._shutter_name = user_input[CONF_NAME]
            self._shutter_channels = user_input["channels"]

            # Validate channels input
            try:
                channels = [int(ch.strip()) for ch in self._shutter_channels.split(",")]
            except ValueError:
                _errors["channels"] = "invalid_channels"
                return await self._show_shutter_form(user_input, _errors)

            # Store the shutter configuration
            self._shutters[self._shutter_name] = self._shutter_channels

            # Ask the user if they want to add another shutter
            if user_input.get("add_another"):
                return await self.async_step_shutter()
            else:
                # All shutters added, create the entry
                return self.async_create_entry(
                    title=self._host,
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_PIN: self._pin,
                        CONF_SHUTTERS: self._shutters,
                    },
                )

        return await self._show_shutter_form(user_input, _errors)

    async def _show_shutter_form(self, user_input, errors):
        """Show the form to input a shutter."""
        return self.async_show_form(
            step_id="shutter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=(user_input or {}).get(CONF_NAME, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        "channels",
                        default=(user_input or {}).get("channels", ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            multiline=False,
                        ),
                    ),
                    vol.Optional(
                        "add_another",
                        default=True,
                    ): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, host: str, port: int, pin: str) -> None:
        """Validate credentials."""
        client = HeytechApiClient(host=host, port=int(port), pin=pin)
        await client.async_test_connection()
