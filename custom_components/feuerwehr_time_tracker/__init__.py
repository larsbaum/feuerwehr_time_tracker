"""Feuerwehr Zeit-Tracker integration."""
from __future__ import annotations

import logging
import os

import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, Event, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    PLATFORMS,
    CARD_VERSION,
    SERVICE_RESET,
    SERVICE_ADD_MINUTES,
    SERVICE_RESET_COUNT,
    SERVICE_ADD_COUNT,
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
    UNDO_ACTION_PREFIX,
    EVENT_MOBILE_APP_NOTIFICATION_ACTION,
    EVENT_IOS_NOTIFICATION_ACTION,
)
from .coordinator import FeuerwehrCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_RESET_SCHEMA = vol.Schema({
    vol.Required("category"): vol.In(["einsatz", "probe", "sonstiges", "all"]),
    vol.Optional("entry_id"): str,
})

SERVICE_ADD_MINUTES_SCHEMA = vol.Schema({
    vol.Required("category"): vol.In(["einsatz", "probe", "sonstiges"]),
    vol.Required("minutes"): vol.Coerce(int),
    vol.Optional("entry_id"): str,
})

SERVICE_RESET_COUNT_SCHEMA = vol.Schema({
    vol.Required("category"): vol.In(["gesamt", "abgerueckt", "bereitschaft", "all"]),
    vol.Optional("entry_id"): str,
})

SERVICE_ADD_COUNT_SCHEMA = vol.Schema({
    vol.Required("category"): vol.In(["gesamt", "abgerueckt", "bereitschaft"]),
    vol.Required("count"): vol.Coerce(int),
    vol.Optional("entry_id"): str,
})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register frontend card early, before any config entry loads."""
    hass.data.setdefault(DOMAIN, {})

    js_path = os.path.join(
        os.path.dirname(__file__), "frontend", "feuerwehr-time-tracker-card.js"
    )
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            f"/{DOMAIN}/feuerwehr-time-tracker-card.js",
            js_path,
            cache_headers=False,
        )
    ])
    add_extra_js_url(hass, f"/{DOMAIN}/feuerwehr-time-tracker-card.js?v={CARD_VERSION}")

    return True


# Key under which the undo-notification listener unsubscribe callbacks are stored
# (kept OUT of hass.data[DOMAIN], which must stay a pure coordinator map).
UNDO_LISTENERS_KEY = f"{DOMAIN}_undo_listeners"


def _register_undo_listener(hass: HomeAssistant) -> None:
    """Listen for a tapped notification action and route it to a coordinator.

    Registered on config-entry setup (not just HA start) so it also works after
    a plain integration reload. The cross-platform companion-app event carries
    the identifier under "action"; the older iOS-only event uses "actionName".
    iOS returns identifiers UPPERCASE, so we uppercase before matching.
    """

    @callback
    def _handle_notification_action(event: Event) -> None:
        raw = event.data.get("action") or event.data.get("actionName") or ""
        # Debug: every notification-action event we receive (enable via
        # logger: custom_components.feuerwehr_time_tracker: debug).
        _LOGGER.debug(
            "Notification action event '%s' received: %s", event.event_type, event.data
        )
        action = raw.upper()
        if not action.startswith(UNDO_ACTION_PREFIX):
            return
        token = action[len(UNDO_ACTION_PREFIX):]
        for coordinator in list(hass.data.get(DOMAIN, {}).values()):
            if coordinator.try_undo(token):
                _LOGGER.info("Undo applied for token %s", token)
                return
        # WARNING so it shows up in Settings → System → Logs without enabling debug.
        _LOGGER.warning(
            "Undo action '%s' received but no pending record matched (token %s)",
            raw,
            token,
        )

    hass.data[UNDO_LISTENERS_KEY] = [
        hass.bus.async_listen(
            EVENT_MOBILE_APP_NOTIFICATION_ACTION, _handle_notification_action
        ),
        hass.bus.async_listen(
            EVENT_IOS_NOTIFICATION_ACTION, _handle_notification_action
        ),
    ]
    _LOGGER.info(
        "Feuerwehr Zeit-Tracker: undo listener registered (%s, %s)",
        EVENT_MOBILE_APP_NOTIFICATION_ACTION,
        EVENT_IOS_NOTIFICATION_ACTION,
    )


@callback
def _async_migrate_geratehaus_entity(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate the legacy 'geratehaus' sensor to the new 'sonstiges' identity.

    Renames unique_id `<entry_id>_geratehaus` -> `<entry_id>_sonstiges` and
    (if free) the entity_id `sensor.station_hours` -> `sensor.other_hours`.
    Idempotent: after the first run the legacy unique_id no longer exists.
    """
    registry = er.async_get(hass)
    old_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_geratehaus"
    )
    if old_entity_id is None:
        return

    new_unique_id = f"{entry.entry_id}_sonstiges"

    # If the target unique_id already exists, the "sonstiges" identity is already
    # present (e.g. a fresh sensor was created before/alongside this legacy one).
    # The old geratehaus entity is now an orphan – renaming it would clash on the
    # unique_id (ValueError) and abort setup. Remove the orphan instead; the
    # counter values live in the coordinator's Store, not in this entity.
    existing_sonstiges = registry.async_get_entity_id(
        "sensor", DOMAIN, new_unique_id
    )
    if existing_sonstiges is not None:
        registry.async_remove(old_entity_id)
        _LOGGER.warning(
            "Removed orphaned legacy entity %s – '_sonstiges' identity already "
            "exists as %s (no data lost, counters live in storage)",
            old_entity_id,
            existing_sonstiges,
        )
        return

    new_entity_id = "sensor.other_hours"
    if registry.async_get(new_entity_id) is not None:
        # entity_id already taken (e.g. second config entry) – keep the old
        # entity_id, only migrate the unique_id.
        registry.async_update_entity(old_entity_id, new_unique_id=new_unique_id)
        _LOGGER.warning(
            "Migrated unique_id of %s to '_sonstiges', but %s is already taken – "
            "entity_id was kept",
            old_entity_id,
            new_entity_id,
        )
    else:
        registry.async_update_entity(
            old_entity_id,
            new_unique_id=new_unique_id,
            new_entity_id=new_entity_id,
        )
        _LOGGER.info(
            "Migrated entity %s -> %s (unique_id '_geratehaus' -> '_sonstiges')",
            old_entity_id,
            new_entity_id,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Feuerwehr Zeit-Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # One-time migration of the renamed "Gerätehaus" -> "Sonstiges" sensor
    _async_migrate_geratehaus_entity(hass, entry)

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

    # Register the undo-notification event listener (only once). Done here rather
    # than in async_setup so it is also (re-)registered after a plain reload.
    if UNDO_LISTENERS_KEY not in hass.data:
        _register_undo_listener(hass)

    _LOGGER.info("Feuerwehr Zeit-Tracker setup complete for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: FeuerwehrCoordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove services and the undo listener if no more coordinator entries remain
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_RESET)
        hass.services.async_remove(DOMAIN, SERVICE_ADD_MINUTES)
        hass.services.async_remove(DOMAIN, SERVICE_RESET_COUNT)
        hass.services.async_remove(DOMAIN, SERVICE_ADD_COUNT)
        for unsub in hass.data.pop(UNDO_LISTENERS_KEY, []):
            unsub()

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

    async def handle_reset_count(call: ServiceCall) -> None:
        category = call.data["category"]
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(hass, entry_id)
        if coordinator:
            coordinator.reset_count(category)
            _LOGGER.info("Service reset_count called: category=%s", category)
        else:
            _LOGGER.warning("reset_count: no coordinator found (entry_id=%s)", entry_id)

    async def handle_add_count(call: ServiceCall) -> None:
        category = call.data["category"]
        count = call.data["count"]
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(hass, entry_id)
        if coordinator:
            coordinator.add_count(category, count)
            _LOGGER.info("Service add_count: category=%s, count=%d", category, count)
        else:
            _LOGGER.warning("add_count: no coordinator found (entry_id=%s)", entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_RESET, handle_reset, schema=SERVICE_RESET_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_MINUTES, handle_add_minutes, schema=SERVICE_ADD_MINUTES_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_COUNT, handle_reset_count, schema=SERVICE_RESET_COUNT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_COUNT, handle_add_count, schema=SERVICE_ADD_COUNT_SCHEMA
    )
