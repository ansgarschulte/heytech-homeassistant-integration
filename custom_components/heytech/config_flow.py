"""
Config flow for the Heytech integration.

This module provides configuration flow handlers for
setting up Heytech devices in Home Assistant.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import selector

from .api import (
    IntegrationHeytechApiClientCommunicationError,
    IntegrationHeytechApiClientError,
)
from .const import CONF_MAX_AUTO_SHUTTERS, CONF_PIN, CONF_SHUTTERS, DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant import data_entry_flow


class HeytechFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Heytech."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Heytech flow handler."""
        self._host: str | None = None
        self._port: int | None = None
        self._pin: str | None = None
        self._max_auto_shutters: int | None = None
        self._add_custom_shutters: bool = False
        self._shutters: dict[str, str] = {}
        self._shutter_name: str | None = None
        self._shutter_channels: str | None = None

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return HeytechOptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by the user."""
        _errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = int(user_input.get(CONF_PORT, "1002"))
            self._pin = user_input.get(CONF_PIN, "")
            self._max_auto_shutters = user_input.get(CONF_MAX_AUTO_SHUTTERS, 10)
            self._add_custom_shutters = user_input.get("add_custom_shutters", False)

            # Validate connection
            try:
                await self._test_credentials(self._host, self._port, self._pin)
            except IntegrationHeytechApiClientCommunicationError as exception:
                LOGGER.error("Communication error: %s", exception)
                _errors["base"] = "connection"
            except IntegrationHeytechApiClientError as exception:
                LOGGER.exception("Unknown error: %s", exception)
                _errors["base"] = "unknown"
            else:
                # Proceed to shutters configuration step
                # if the user opts to add custom shutters
                if self._add_custom_shutters:
                    return await self.async_step_shutter()

                # Skip custom shutters and create the entry directly
                return self.async_create_entry(
                    title=self._host or "Heytech",
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_PIN: self._pin,
                        CONF_MAX_AUTO_SHUTTERS: self._max_auto_shutters,
                        CONF_SHUTTERS: {},  # No custom shutters
                    },
                )

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
                    vol.Optional(
                        CONF_MAX_AUTO_SHUTTERS,
                        default=(user_input or {}).get(CONF_MAX_AUTO_SHUTTERS, 10),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=50,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        "add_custom_shutters", default=False
                    ): selector.BooleanSelector(),
                },
            ),
            errors=_errors,
        )

    async def async_step_shutter(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Step to add shutters."""
        _errors: dict[str, str] = {}
        if user_input is not None:
            self._shutter_name = user_input[CONF_NAME]
            self._shutter_channels = user_input["channels"]

            # Validate channels input
            try:
                [int(ch.strip()) for ch in self._shutter_channels.split(",")]
            except ValueError:
                _errors["channels"] = "invalid_channels"
                return await self._show_shutter_form(user_input, _errors)

            # Store the shutter configuration
            self._shutters[self._shutter_name] = self._shutter_channels

            # Ask the user if they want to add another shutter
            if user_input.get("add_another"):
                return await self.async_step_shutter()

            # All shutters added, create the entry
            return self.async_create_entry(
                title=self._host or "Heytech",
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: int(self._port),
                    CONF_PIN: self._pin,
                    CONF_MAX_AUTO_SHUTTERS: self._max_auto_shutters,
                    CONF_SHUTTERS: self._shutters,
                },
            )

        return await self._show_shutter_form(user_input, _errors)

    async def _show_shutter_form(
        self, user_input: dict[str, Any] | None, errors: dict[str, str]
    ) -> data_entry_flow.FlowResult:
        """Show the form to input a shutter."""
        return self.async_show_form(
            step_id="shutter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=(user_input or {}).get(CONF_NAME, "")
                    ): selector.TextSelector(),
                    vol.Required(
                        "channels", default=(user_input or {}).get("channels", "")
                    ): selector.TextSelector(),
                    vol.Optional(
                        "add_another", default=True
                    ): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, host: str, port: int, pin: str) -> None:
        """Validate credentials."""


class HeytechOptionsFlowHandler(OptionsFlow):
    """Handle Heytech options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Heytech options flow."""
        self._config_entry = config_entry
        self._shutters: dict[str, str] = dict(
            config_entry.options.get(
                CONF_SHUTTERS,
                config_entry.data.get(CONF_SHUTTERS, {}),
            )
        )
        self._shutter_name: str | None = None
        self._shutter_channels: str | None = None

    async def async_step_init(
        self, _user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Manage the options."""
        return await self.async_step_shutter_menu()

    async def async_step_shutter_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Menu for managing shutters."""
        if user_input is not None:
            menu_option = user_input["menu_option"]
            if menu_option == "add_shutter":
                return await self.async_step_add_shutter()
            if menu_option == "remove_shutter":
                return await self.async_step_remove_shutter()
            if menu_option == "export_config":
                return await self.async_step_export_config()
            if menu_option == "import_config":
                return await self.async_step_import_config()
            if menu_option == "finish":
                # Check if shutters have changed
                original_shutters = self._config_entry.options.get(
                    CONF_SHUTTERS,
                    self._config_entry.data.get(CONF_SHUTTERS, {}),
                )
                if self._shutters != original_shutters:
                    return self.async_create_entry(
                        title="",
                        data={CONF_SHUTTERS: self._shutters},
                    )
                return self.async_abort(reason="no_changes")
        options = [
            ("add_shutter", "Add Shutter"),
            ("remove_shutter", "Remove Shutter"),
            ("export_config", "Export Configuration"),
            ("import_config", "Import Configuration"),
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

    async def async_step_add_shutter(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Add a shutter."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._shutter_name = user_input[CONF_NAME]
            self._shutter_channels = user_input["channels"]
            # Validate channels input
            try:
                [int(ch.strip()) for ch in self._shutter_channels.split(",")]
            except ValueError:
                errors["channels"] = "invalid_channels"
                return await self._show_add_shutter_form(user_input, errors)
            # Add shutter to shutters dict
            self._shutters[self._shutter_name] = self._shutter_channels
            # Ask if the user wants to add another shutter
            if user_input.get("add_another"):
                return await self.async_step_add_shutter()
            return await self.async_step_shutter_menu()
        return await self._show_add_shutter_form(user_input, errors)

    async def _show_add_shutter_form(
        self, user_input: dict[str, Any] | None, errors: dict[str, str]
    ) -> data_entry_flow.FlowResult:
        """Show the form to add a shutter."""
        return self.async_show_form(
            step_id="add_shutter",
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

    async def async_step_remove_shutter(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Remove a shutter."""
        errors: dict[str, str] = {}
        if not self._shutters:
            return self.async_abort(reason="no_shutters_to_remove")
        if user_input is not None:
            shutter_to_remove = user_input["shutter"]
            if shutter_to_remove in self._shutters:
                del self._shutters[shutter_to_remove]
                return await self.async_step_shutter_menu()
            errors["shutter"] = "shutter_not_found"
        data_schema = vol.Schema(
            {
                vol.Required("shutter"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": name, "label": name} for name in self._shutters
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

    async def async_step_export_config(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Export shutters configuration."""
        if user_input is not None:
            return await self.async_step_shutter_menu()
        
        # Create export data
        export_data = {
            "version": "1.0",
            "shutters": self._shutters,
        }
        
        export_json = json.dumps(export_data, indent=2)
        
        # Show export data to user
        return self.async_show_form(
            step_id="export_config",
            data_schema=vol.Schema({}),
            description_placeholders={
                "config_data": export_json,
                "count": str(len(self._shutters)),
            },
        )

    async def async_step_import_config(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Import shutters configuration."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                # Parse JSON data
                import_data = json.loads(user_input["config_data"])
                
                if "shutters" not in import_data:
                    errors["config_data"] = "invalid_format"
                else:
                    # Validate shutters format
                    shutters = import_data["shutters"]
                    if not isinstance(shutters, dict):
                        errors["config_data"] = "invalid_format"
                    else:
                        # Merge imported shutters with existing ones
                        self._shutters.update(shutters)
                        return await self.async_step_shutter_menu()
                        
            except json.JSONDecodeError:
                errors["config_data"] = "invalid_json"
        
        return self.async_show_form(
            step_id="import_config",
            data_schema=vol.Schema(
                {
                    vol.Required("config_data"): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            multiline=True,
                        ),
                    ),
                }
            ),
            errors=errors,
        )
