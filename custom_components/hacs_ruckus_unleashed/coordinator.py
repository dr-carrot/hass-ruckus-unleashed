"""DataUpdateCoordinator for the Ruckus Unleashed integration."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, AsyncIterator

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .session import create_client_session, verify_ssl_from_data

_LOGGER = logging.getLogger(__name__)


@dataclass
class RuckusData:
    """Data retrieved from the Ruckus Unleashed controller."""

    aps: list[dict[str, Any]]
    wlans: list[dict[str, Any]]


class RuckusDataUpdateCoordinator(DataUpdateCoordinator[RuckusData]):
    """Coordinate polling of a Ruckus Unleashed controller."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.config_entry = entry
        self._verify_ssl = self._get_option(
            CONF_VERIFY_SSL, verify_ssl_from_data(entry.data)
        )
        self.update_interval = timedelta(seconds=self.scan_interval)

    @property
    def host(self) -> str:
        """Return the controller host from the config entry."""
        return self.config_entry.data[CONF_HOST]

    @property
    def username(self) -> str:
        """Return the username from the config entry."""
        return self.config_entry.data[CONF_USERNAME]

    @property
    def password(self) -> str:
        """Return the password from the config entry."""
        return self.config_entry.data[CONF_PASSWORD]

    @property
    def scan_interval(self) -> int:
        """Return the configured scan interval (options first, then data)."""
        return self._get_option(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    def _get_option(self, key: str, default: Any) -> Any:
        """Read an option, falling back to the entry data value."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )

    def update_settings(self) -> None:
        """Apply new option values (verify_ssl, scan_interval)."""
        self._verify_ssl = self._get_option(
            CONF_VERIFY_SSL, verify_ssl_from_data(self.config_entry.data)
        )
        self.update_interval = timedelta(seconds=self.scan_interval)
        _LOGGER.debug(
            "Settings updated: verify_ssl=%s scan_interval=%s",
            self._verify_ssl,
            self.scan_interval,
        )

    async def _async_fetch(
        self, method_name: str | None = None, args: tuple = ()
    ) -> dict | None:
        """Open a session and run a command, closing the session afterwards.

        Returns None when ``method_name`` is None (used for bare login tests).
        """
        async with self._session_context() as ruckus:
            if method_name is None:
                return None
            return await getattr(ruckus.api, method_name)(*args)

    @asynccontextmanager
    async def _session_context(self) -> AsyncIterator[Any]:
        """Context manager yielding an authenticated AjaxSession."""
        from aioruckus import AjaxSession
        from aioruckus.exceptions import AuthenticationError

        websession = create_client_session(self._verify_ssl)
        try:
            async with AjaxSession(
                websession,
                self.host,
                self.username,
                self.password,
                auto_cleanup_websession=True,
            ) as ruckus:
                yield ruckus
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Authentication with controller failed") from err
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as err:
            raise UpdateFailed(f"Error communicating with controller: {err}") from err
        finally:
            if not websession.closed:
                await websession.close()

    async def _async_update_data(self) -> RuckusData:
        async with self._session_context() as ruckus:
            aps, wlans = await asyncio.gather(
                ruckus.api.get_aps(),
                ruckus.api.get_wlans(),
            )
        aps = aps or []
        wlans = wlans or []
        _LOGGER.debug(
            "Controller data: %d AP(s), %d WLAN(s)",
            len(aps),
            len(wlans),
        )
        for wlan in wlans:
            _LOGGER.debug(
                "WLAN id=%s name=%s enable-type=%r",
                wlan.get("id"),
                wlan.get("name"),
                wlan.get("enable-type"),
            )
        return RuckusData(aps=aps, wlans=wlans)

    async def async_enable_wlan(self, name: str) -> None:
        """Enable a WLAN by name, then refresh immediately."""
        await self._async_command("do_enable_wlan", name, "WLAN")

    async def async_disable_wlan(self, name: str) -> None:
        """Disable a WLAN by name, then refresh immediately."""
        await self._async_command("do_disable_wlan", name, "WLAN")

    async def async_show_ap_leds(self, mac: str) -> None:
        """Show an AP's LEDs, then refresh immediately."""
        await self._async_command("do_show_ap_leds", mac, "AP LED")

    async def async_hide_ap_leds(self, mac: str) -> None:
        """Hide an AP's LEDs, then refresh immediately."""
        await self._async_command("do_hide_ap_leds", mac, "AP LED")

    async def _async_command(
        self, command: str, target: str, label: str
    ) -> None:
        """Run a command and refresh, translating failures to HA errors."""
        try:
            await self._async_fetch(command, (target,))
        except ConfigEntryAuthFailed:
            raise
        except (UpdateFailed, ValueError, RuntimeError) as err:
            raise HomeAssistantError(
                f"Failed to {command.replace('do_', '').replace('_', ' ')} "
                f"{label} {target}: {err}"
            ) from err
        await self.async_request_refresh()
