"""Switches for the Ruckus Unleashed integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
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
    """Set up Ruckus Unleashed WLAN and AP LED switches."""
    coordinator: RuckusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_wlan_ids: set[str] = set()
    known_ap_serials: set[str] = set()

    def _discover_wlans() -> None:
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

    def _discover_ap_leds() -> None:
        """Add entities for any newly discovered APs."""
        aps = coordinator.data.aps if coordinator.data else []
        new_entities = [
            RuckusApLedSwitch(coordinator, ap)
            for ap in aps
            if ap.get("serial") not in known_ap_serials
        ]
        if not new_entities:
            return
        for ap in aps:
            if serial := ap.get("serial"):
                known_ap_serials.add(serial)
        async_add_entities(new_entities)
        _LOGGER.debug(
            "Discovered %d new AP LED switch(es) across %d AP(s)",
            len(new_entities),
            len(known_ap_serials),
        )

    _discover_wlans()
    _discover_ap_leds()
    remove_wlan_listener = coordinator.async_add_listener(_discover_wlans)
    remove_ap_led_listener = coordinator.async_add_listener(_discover_ap_leds)
    entry.async_on_unload(remove_wlan_listener)
    entry.async_on_unload(remove_ap_led_listener)


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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        )

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


class RuckusApLedSwitch(CoordinatorEntity[RuckusDataUpdateCoordinator], SwitchEntity):
    """A switch controlling a single physical AP's LEDs."""

    _attr_has_entity_name = True
    _attr_name = "LEDs"

    def __init__(
        self,
        coordinator: RuckusDataUpdateCoordinator,
        ap: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._serial = ap["serial"]
        self._mac = ap["mac"]
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ap_led_{self._serial}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
        )

    @property
    def _ap(self) -> dict[str, Any] | None:
        """Return the current AP data for this entity, if still present."""
        return next(
            (
                ap
                for ap in self.coordinator.data.aps
                if ap.get("serial") == self._serial
            ),
            None,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the LED state.

        ``led-off`` is ``"false"`` when LEDs are visible, ``"true"`` when hidden,
        and ``"*"`` when inherited from the AP group config (state unknown).
        """
        ap = self._ap
        if ap is None:
            return None
        led_off = ap.get("led-off")
        if led_off == "true":
            return False
        if led_off == "false":
            return True
        return None

    @property
    def available(self) -> bool:
        """Report available only when the coordinator is healthy and the AP
        is still present in the latest poll."""
        return self.coordinator.last_update_success and self._ap is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw led-off value for debugging."""
        ap = self._ap or {}
        return {"led_off": ap.get("led-off")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Show the AP's LEDs."""
        if self._ap is None:
            return
        await self.coordinator.async_show_ap_leds(self._mac)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Hide the AP's LEDs."""
        if self._ap is None:
            return
        await self.coordinator.async_hide_ap_leds(self._mac)
