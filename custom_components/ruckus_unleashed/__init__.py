"""The Ruckus Unleashed integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER, PLATFORMS
from .coordinator import RuckusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ruckus Unleashed from a config entry."""
    coordinator = RuckusDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    def _register_aps() -> None:
        _register_ap_devices(hass, entry, coordinator)

    _register_aps()
    coordinator.async_add_listener(_register_aps)
    entry.async_on_unload(coordinator.async_remove_listener(_register_aps))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Apply option changes without reloading the integration."""
    coordinator: RuckusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.update_settings()
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _register_ap_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: RuckusDataUpdateCoordinator
) -> None:
    """Create one Home Assistant device per physical AP."""
    registry = dr.async_get(hass)
    for ap in coordinator.data.aps:
        serial = ap.get("serial")
        if not serial:
            continue
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            model=ap.get("model"),
            name=ap.get("devname") or ap.get("name") or serial,
            sw_version=ap.get("version"),
        )
