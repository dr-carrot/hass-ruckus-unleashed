"""Buttons for the Ruckus Unleashed integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
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
    """Set up Ruckus Unleashed AP LED buttons."""
    coordinator: RuckusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_ap_serials: set[str] = set()

    def _discover() -> None:
        """Add entities for any newly discovered APs."""
        aps = coordinator.data.aps if coordinator.data else []
        new_entities = [
            RuckusApShowLedsButton(coordinator, ap)
            for ap in aps
            if ap.get("serial") not in known_ap_serials
        ]
        new_entities.extend(
            RuckusApHideLedsButton(coordinator, ap)
            for ap in aps
            if ap.get("serial") not in known_ap_serials
        )
        if not new_entities:
            return
        for ap in aps:
            if serial := ap.get("serial"):
                known_ap_serials.add(serial)
        async_add_entities(new_entities)
        _LOGGER.debug(
            "Discovered %d new AP LED button(s) across %d AP(s)",
            len(new_entities),
            len(known_ap_serials),
        )

    _discover()
    remove_discover_listener = coordinator.async_add_listener(_discover)
    entry.async_on_unload(remove_discover_listener)


class _RuckusApLedButton(CoordinatorEntity[RuckusDataUpdateCoordinator], ButtonEntity):
    """Base button for AP LED actions."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RuckusDataUpdateCoordinator,
        ap: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._serial = ap["serial"]
        self._mac = ap["mac"]
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
    def available(self) -> bool:
        """Report available only when the coordinator is healthy and the AP
        is still present in the latest poll."""
        return self.coordinator.last_update_success and self._ap is not None


class RuckusApShowLedsButton(_RuckusApLedButton):
    """Button to show an AP's LEDs."""

    _attr_name = "Show LEDs"

    def __init__(
        self,
        coordinator: RuckusDataUpdateCoordinator,
        ap: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, ap)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ap_show_leds_{self._serial}"

    async def async_press(self) -> None:
        """Show the AP's LEDs."""
        await self.coordinator.async_show_ap_leds(self._mac)


class RuckusApHideLedsButton(_RuckusApLedButton):
    """Button to hide an AP's LEDs."""

    _attr_name = "Hide LEDs"

    def __init__(
        self,
        coordinator: RuckusDataUpdateCoordinator,
        ap: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, ap)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ap_hide_leds_{self._serial}"

    async def async_press(self) -> None:
        """Hide the AP's LEDs."""
        await self.coordinator.async_hide_ap_leds(self._mac)
