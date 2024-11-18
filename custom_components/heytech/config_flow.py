"""Adds config flow for Heytech."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.helpers import selector

from . import HeytechApiClient
from .api import (
    IntegrationHeytechApiClientCommunicationError,
    IntegrationHeytechApiClientError,
)
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

    @staticmethod
    def async_get_options_flow(config_entry):
        return HeytechOptionsFlowHandler(config_entry)

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


class HeytechOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Heytech options."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize Heytech options flow."""
        self.config_entry = config_entry
        self._shutters = dict(
            self.config_entry.options.get(
                CONF_SHUTTERS, self.config_entry.data.get(CONF_SHUTTERS, {})
            )
        )
        self._shutter_name = None
        self._shutter_channels = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_shutter_menu()

    async def async_step_shutter_menu(self, user_input=None):
        """Menu for managing shutters."""
        if user_input is not None:
            if user_input["menu_option"] == "add_shutter":
                return await self.async_step_add_shutter()
            elif user_input["menu_option"] == "remove_shutter":
                return await self.async_step_remove_shutter()
            elif user_input["menu_option"] == "finish":
                # Check if shutters have changed
                if self._shutters != self.config_entry.options.get(
                        CONF_SHUTTERS, self.config_entry.data.get(CONF_SHUTTERS, {})
                ):
                    return self.async_create_entry(
                        title="", data={CONF_SHUTTERS: self._shutters}
                    )
                else:
                    return self.async_abort(reason="no_changes")
        options = [
            ("add_shutter", "Add Shutter"),
            ("remove_shutter", "Remove Shutter"),
            ("finish", "Finish"),
        ]
        data_schema = vol.Schema(
            {
                vol.Required("menu_option"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": val, "label": label} for val, label in options
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="shutter_menu",
            data_schema=data_schema,
        )

    async def async_step_add_shutter(self, user_input=None):
        """Add a shutter."""
        errors = {}
        if user_input is not None:
            self._shutter_name = user_input[CONF_NAME]
            self._shutter_channels = user_input["channels"]
            # Validate channels input
            try:
                channels = [
                    int(ch.strip()) for ch in self._shutter_channels.split(",")
                ]
            except ValueError:
                errors["channels"] = "invalid_channels"
                return await self._show_add_shutter_form(user_input, errors)
            # Add shutter to shutters dict
            self._shutters[self._shutter_name] = self._shutter_channels
            # Ask if the user wants to add another shutter
            if user_input.get("add_another"):
                return await self.async_step_add_shutter()
            else:
                return await self.async_step_shutter_menu()
        return await self._show_add_shutter_form(user_input, errors)

    async def _show_add_shutter_form(self, user_input, errors):
        return self.async_show_form(
            step_id="add_shutter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=(user_input or {}).get(CONF_NAME, "")
                    ): str,
                    vol.Required(
                        "channels", default=(user_input or {}).get("channels", "")
                    ): str,
                    vol.Optional("add_another", default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_remove_shutter(self, user_input=None):
        """Remove a shutter."""
        errors = {}
        if not self._shutters:
            return self.async_abort(reason="no_shutters_to_remove")
        if user_input is not None:
            shutter_to_remove = user_input["shutter"]
            if shutter_to_remove in self._shutters:
                del self._shutters[shutter_to_remove]
                return await self.async_step_shutter_menu()
            else:
                errors["shutter"] = "shutter_not_found"
        data_schema = vol.Schema(
            {
                vol.Required("shutter"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": name, "label": name}
                            for name in self._shutters.keys()
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="remove_shutter",
            data_schema=data_schema,
            errors=errors,
        )