"""Adds config flow for Heytech."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.helpers import selector
from homeassistant.core import callback

from . import HeytechApiClient
from .api import IntegrationHeytechApiClientCommunicationError, IntegrationHeytechApiClientError
from .const import DOMAIN, LOGGER, CONF_PIN, CONF_SHUTTERS

_LOGGER = logging.getLogger(__name__)

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return HeytechOptionsFlowHandler(config_entry)

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


class HeytechOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Heytech options."""

    def __init__(self, config_entry):
        """Initialize Heytech options flow."""
        self.config_entry = config_entry
        self._host = config_entry.data.get(CONF_HOST)
        self._port = config_entry.data.get(CONF_PORT)
        self._pin = config_entry.data.get(CONF_PIN, "")
        self._shutters = dict(config_entry.options.get(CONF_SHUTTERS, config_entry.data.get(CONF_SHUTTERS, {})))

    async def async_step_init(self, user_input=None):
        """Manage the Heytech options."""
        return await self.async_step_shutter_menu()

    async def async_step_shutter_menu(self, user_input=None):
        """Display the options menu for shutters."""
        return self.async_show_menu(
            step_id="shutter_menu",
            menu_options=["add_shutter", "remove_shutter", "finish"],
        )

    async def async_step_add_shutter(self, user_input=None):
        """Step to add a shutter."""
        errors = {}
        if user_input is not None:
            shutter_name = user_input[CONF_NAME]
            shutter_channels = user_input["channels"]

            # Validate channels input
            try:
                channels = [int(ch.strip()) for ch in shutter_channels.split(",")]
            except ValueError:
                errors["channels"] = "invalid_channels"
                return await self._show_add_shutter_form(user_input, errors)

            # Add the shutter
            self._shutters[shutter_name] = shutter_channels

            # Ask if the user wants to add another shutter
            if user_input.get("add_another"):
                return await self.async_step_add_shutter()
            else:
                # Save the updated shutters and finish
                return await self._update_options()

        return await self._show_add_shutter_form(user_input, errors)

    async def async_step_remove_shutter(self, user_input=None):
        """Step to remove a shutter."""
        if user_input is not None:
            shutter_name = user_input["shutter"]
            if shutter_name in self._shutters:
                del self._shutters[shutter_name]
            return await self._update_options()

        shutters_list = list(self._shutters.keys())
        if not shutters_list:
            return self.async_abort(reason="no_shutters_to_remove")

        return self.async_show_form(
            step_id="remove_shutter",
            data_schema=vol.Schema({
                vol.Required("shutter"): vol.In(shutters_list),
            }),
        )

    async def async_step_finish(self, user_input=None):
        """Finish the options flow."""
        _LOGGER.debug("Finishing options flow and updating options.")
        return await self._update_options()

    async def _update_options(self):
        """Update config entry options."""
        new_options = {
            **self.config_entry.options,
            CONF_SHUTTERS: self._shutters,
        }
        _LOGGER.info(f"Updating options: {new_options}")
        self.hass.config_entries.async_update_entry(
            self.config_entry, options=new_options
        )
        return self.async_create_entry(title="", data={})

    async def _show_add_shutter_form(self, user_input, errors):
        """Show the form to input a new shutter."""
        return self.async_show_form(
            step_id="add_shutter",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=(user_input or {}).get(CONF_NAME, "")): selector.TextSelector(),
                vol.Required("channels", default=(user_input or {}).get("channels", "")): selector.TextSelector(),
                vol.Optional("add_another", default=False): selector.BooleanSelector(),
            }),
            errors=errors,
        )
