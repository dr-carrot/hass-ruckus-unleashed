"""Switches for the Ruckus Unleashed integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RuckusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ruckus Unleashed WLAN switches."""
    coordinator: RuckusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_wlan_ids: set[str] = set()

    def _discover() -> None:
        """Add entities for any newly discovered WLANs."""
        wlans = coordinator.data.wlans if coordinator.data else []
        new_entities = [
            RuckusWlanSwitch(coordinator, wlan)
            for wlan in wlans
            if wlan["id"] not in known_wlan_ids
        ]
        if not new_entities:
            return
        for wlan in wlans:
            known_wlan_ids.add(wlan["id"])
        async_add_entities(new_entities)
        _LOGGER.debug(
            "Discovered %d new WLAN(s): %s",
            len(new_entities),
            ", ".join(e._attr_name for e in new_entities),
        )

    _discover()
    coordinator.async_add_listener(_discover)
    entry.async_on_unload(coordinator.async_remove_listener(_discover))


class RuckusWlanSwitch(CoordinatorEntity[RuckusDataUpdateCoordinator], SwitchEntity):
    """A switch representing a single Ruckus Unleashed WLAN."""

    def __init__(
        self,
        coordinator: RuckusDataUpdateCoordinator,
        wlan: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._wlan_id = wlan["id"]
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._wlan_id}"
        self._attr_name = wlan["name"]

    @property
    def _wlan(self) -> dict[str, Any] | None:
        """Return the current WLAN data for this entity, if still present."""
        return next(
            (
                wlan
                for wlan in self.coordinator.data.wlans
                if wlan["id"] == self._wlan_id
            ),
            None,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the WLAN enabled state.

        aioruckus' ``do_disable_wlan`` sets ``enable-type`` to ``1`` to disable
        and ``0`` to enable, so an enabled WLAN reports ``enable-type == "0"``.
        """
        wlan = self._wlan
        if wlan is None:
            return None
        return wlan.get("enable-type") == "0"

    @property
    def available(self) -> bool:
        """Report available only when the coordinator is healthy and the WLAN
        is still present in the latest poll."""
        return self.coordinator.last_update_success and self._wlan is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful WLAN metadata."""
        wlan = self._wlan or {}
        return {
            "ssid": wlan.get("ssid"),
            "is_guest": wlan.get("is-guest"),
            "encryption": wlan.get("encryption"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the WLAN."""
        wlan = self._wlan
        if wlan is None:
            return
        await self.coordinator.async_enable_wlan(wlan["name"])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the WLAN."""
        wlan = self._wlan
        if wlan is None:
            return
        await self.coordinator.async_disable_wlan(wlan["name"])
