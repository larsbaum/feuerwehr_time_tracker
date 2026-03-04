"""Feuerwehr Zeit-Tracker integration."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_RESET,
    SERVICE_ADD_MINUTES,
    CONF_PERSON,
    CONF_ZONE,
    CONF_ALARM,
    CONF_PROBE_WEEKDAY,
    CONF_PROBE_START,
    CONF_PROBE_END,
    CONF_PROBE_COUNT_START,
    CONF_PROBE_COUNT_END,
    CONF_EINSATZ_MAX_HOURS,
    CONF_NOTIFY_SERVICE,
)
from .coordinator import FeuerwehrCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_RESET_SCHEMA = vol.Schema({
    vol.Required("category"): vol.In(["einsatz", "probe", "geratehaus", "all"]),
    vol.Optional("entry_id"): str,
})

SERVICE_ADD_MINUTES_SCHEMA = vol.Schema({
    vol.Required("category"): vol.In(["einsatz", "probe", "geratehaus"]),
    vol.Required("minutes"): vol.Coerce(int),
    vol.Optional("entry_id"): str,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Feuerwehr Zeit-Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Merge entry.data and entry.options (options override data on reconfigure)
    config = {**entry.data, **entry.options}

    coordinator = FeuerwehrCoordinator(hass, entry.entry_id, config)
    await coordinator.async_setup()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register entry update listener (for options flow)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register services (only once, regardless of how many entries exist)
    if not hass.services.has_service(DOMAIN, SERVICE_RESET):
        _register_services(hass)

    _LOGGER.info("Feuerwehr Zeit-Tracker setup complete for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: FeuerwehrCoordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove services if no more entries
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_RESET)
        hass.services.async_remove(DOMAIN, SERVICE_ADD_MINUTES)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update – reload entry to apply new config."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_coordinator(hass: HomeAssistant, entry_id: str | None) -> FeuerwehrCoordinator | None:
    """Get coordinator by entry_id, or the first one if only one exists."""
    entries = hass.data.get(DOMAIN, {})
    if entry_id and entry_id in entries:
        return entries[entry_id]
    if len(entries) == 1:
        return next(iter(entries.values()))
    return None


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    async def handle_reset(call: ServiceCall) -> None:
        category = call.data["category"]
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(hass, entry_id)
        if coordinator:
            coordinator.reset_category(category)
            _LOGGER.info("Service reset called: category=%s", category)
        else:
            _LOGGER.warning("reset: no coordinator found (entry_id=%s)", entry_id)

    async def handle_add_minutes(call: ServiceCall) -> None:
        category = call.data["category"]
        minutes = call.data["minutes"]
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(hass, entry_id)
        if coordinator:
            coordinator.add_minutes(category, minutes)
            _LOGGER.info("Service add_minutes: category=%s, minutes=%d", category, minutes)
        else:
            _LOGGER.warning("add_minutes: no coordinator found (entry_id=%s)", entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_RESET, handle_reset, schema=SERVICE_RESET_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_MINUTES, handle_add_minutes, schema=SERVICE_ADD_MINUTES_SCHEMA
    )
