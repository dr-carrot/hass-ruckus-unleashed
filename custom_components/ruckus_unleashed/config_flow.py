"""Config flow for the Ruckus Unleashed integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .session import create_client_session, verify_ssl_from_data

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Raised when the controller cannot be reached."""


class InvalidAuth(HomeAssistantError):
    """Raised when authentication with the controller fails."""


USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input by connecting to the controller.

    Raises on failure; callers translate exceptions into flow errors.
    """
    from aioruckus import AjaxSession
    from aioruckus.exceptions import AuthenticationError

    websession = create_client_session(data[CONF_VERIFY_SSL])
    try:
        async with AjaxSession(
            websession,
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            auto_cleanup_websession=True,
        ) as ruckus:
            await ruckus.api.get_wlans()
    except AuthenticationError as err:
        raise InvalidAuth from err
    except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as err:
        raise CannotConnect from err
    finally:
        if not websession.closed:
            await websession.close()


def _reauth_schema(entry: ConfigEntry) -> vol.Schema:
    """Build the reauth data schema, pre-filling known values."""
    return vol.Schema(
        {
            vol.Required(
                CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")
            ): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(
                CONF_VERIFY_SSL, default=verify_ssl_from_data(entry.data)
            ): bool,
        }
    )


class RuckusUnleashedConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ruckus Unleashed."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during validation: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication when credentials are rejected."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                await validate_input(self.hass, data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during reauth: %s", err)
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(entry, data=data)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth",
            data_schema=_reauth_schema(entry),
            errors=errors,
        )

    def _get_reauth_entry(self) -> ConfigEntry:
        return self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return RuckusUnleashedOptionsFlow(config_entry)


class RuckusUnleashedOptionsFlow(OptionsFlow):
    """Handle options for the Ruckus Unleashed integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_VERIFY_SSL,
                        default=options.get(
                            CONF_VERIFY_SSL,
                            verify_ssl_from_data(self._config_entry.data),
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL),
                    ),
                }
            ),
        )
