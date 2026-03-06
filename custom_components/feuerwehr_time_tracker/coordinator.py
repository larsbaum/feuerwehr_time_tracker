"""Coordinator for Feuerwehr Zeit-Tracker – handles all tracking logic."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, time as dtime
from typing import Any

from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
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
    DATA_EINSATZ_MINUTES,
    DATA_PROBE_MINUTES,
    DATA_GERATEHAUS_MINUTES,
    DATA_EINSATZ_STARTED,
    DATA_PROBE_STARTED,
    WEEKDAY_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


def _parse_time(t: str) -> dtime:
    """Parse 'HH:MM' string to time object."""
    h, m = t.split(":")
    return dtime(int(h), int(m))


def _in_time_window(now: datetime, start: str, end: str) -> bool:
    """Check if current time is within HH:MM window."""
    t = now.time()
    s = _parse_time(start)
    e = _parse_time(end)
    if s <= e:
        return s <= t <= e
    # overnight window
    return t >= s or t <= e


def _is_probe_weekday(now: datetime, weekday_key: str) -> bool:
    """Check if today is the configured probe weekday."""
    target = WEEKDAY_OPTIONS.get(weekday_key, 1)  # default Tuesday
    return now.weekday() == target


class FeuerwehrCoordinator:
    """
    Central coordinator that:
    - Listens to person zone enter/leave events
    - Runs a per-minute tick for zone-presence counting
    - Persists all data via HA Store
    - Notifies sensors of updates
    """

    def __init__(self, hass: HomeAssistant, entry_id: str, config: dict) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.config = config

        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        self._data: dict[str, Any] = {
            DATA_EINSATZ_MINUTES: 0,
            DATA_PROBE_MINUTES: 0,
            DATA_GERATEHAUS_MINUTES: 0,
            DATA_EINSATZ_STARTED: None,
            DATA_PROBE_STARTED: None,
        }

        self._unsub_zone = None
        self._unsub_timer = None
        self._listeners: list[callback] = []

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def einsatz_minutes(self) -> int:
        return int(self._data.get(DATA_EINSATZ_MINUTES, 0))

    @property
    def probe_minutes(self) -> int:
        return int(self._data.get(DATA_PROBE_MINUTES, 0))

    @property
    def geratehaus_minutes(self) -> int:
        return int(self._data.get(DATA_GERATEHAUS_MINUTES, 0))

    @property
    def gesamt_minutes(self) -> int:
        return self.einsatz_minutes + self.probe_minutes + self.geratehaus_minutes

    def get_cfg(self, key: str, default=None):
        """Get effective config value (options override data)."""
        return self.config.get(key, default)

    def _get_zone_name(self) -> str:
        """Get the zone name as it appears in person.state.

        HA's person entity sets its state to zone_state.name (the friendly
        name), NOT the entity-id slug.  We must compare against the same
        value, otherwise the zone check silently fails.
        """
        zone_entity_id = self.get_cfg(CONF_ZONE, "")
        zone_state = self.hass.states.get(zone_entity_id)
        if zone_state:
            return zone_state.name
        # Fallback when state object is unavailable
        return zone_entity_id.replace("zone.", "")

    # ------------------------------------------------------------------
    # Setup / Teardown
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Load stored data and start listeners."""
        stored = await self._store.async_load()
        if stored:
            self._data.update(stored)
            _LOGGER.debug("Loaded stored data: %s", self._data)

        person = self.get_cfg(CONF_PERSON)

        self._unsub_zone = async_track_state_change_event(
            self.hass, [person], self._handle_person_state_change
        )
        self._unsub_timer = async_track_time_interval(
            self.hass, self._handle_minute_tick, timedelta(minutes=1)
        )
        _LOGGER.info("Feuerwehr Zeit-Tracker coordinator started for %s", person)

    async def async_shutdown(self) -> None:
        """Stop all listeners."""
        if self._unsub_zone:
            self._unsub_zone()
        if self._unsub_timer:
            self._unsub_timer()
        await self._store.async_save(self._data)
        _LOGGER.info("Feuerwehr Zeit-Tracker coordinator stopped.")

    # ------------------------------------------------------------------
    # Zone change handler
    # ------------------------------------------------------------------

    @callback
    def _handle_person_state_change(self, event: Event) -> None:
        """React to person entity state changes (zone enter/leave)."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if not old_state or not new_state:
            return

        zone = self._get_zone_name()
        alarm = self.get_cfg(CONF_ALARM, "")
        now = dt_util.now()

        old_in_zone = old_state.state == zone
        new_in_zone = new_state.state == zone

        # --- LEAVING zone ---
        if old_in_zone and not new_in_zone:
            self._on_zone_leave(now, alarm)

        # --- ENTERING zone ---
        if not old_in_zone and new_in_zone:
            self._on_zone_enter(now)

    def _on_zone_leave(self, now: datetime, alarm_entity: str) -> None:
        """Handle zone leave: set start timestamps if conditions match."""
        alarm_state = self.hass.states.get(alarm_entity)
        alarm_on = alarm_state and alarm_state.state == "on"

        # Einsatz: alarm must be active
        if alarm_on:
            self._data[DATA_EINSATZ_STARTED] = now.timestamp()
            _LOGGER.info("Einsatz started at %s", now)

        # Probe: correct weekday + time window
        probe_weekday = self.get_cfg(CONF_PROBE_WEEKDAY, "tue")
        probe_start = self.get_cfg(CONF_PROBE_START, "17:00")
        probe_end = self.get_cfg(CONF_PROBE_END, "23:59")

        if (
            not alarm_on
            and _is_probe_weekday(now, probe_weekday)
            and _in_time_window(now, probe_start, probe_end)
        ):
            self._data[DATA_PROBE_STARTED] = now.timestamp()
            _LOGGER.info("Probe absence started at %s", now)

        self.hass.async_create_task(self._async_save())

    def _on_zone_enter(self, now: datetime) -> None:
        """Handle zone enter: calculate and add minutes if applicable."""
        max_hours = self.get_cfg(CONF_EINSATZ_MAX_HOURS, 10)

        # --- Einsatz ---
        einsatz_started = self._data.get(DATA_EINSATZ_STARTED)
        if einsatz_started:
            elapsed = now.timestamp() - einsatz_started
            if 0 < elapsed <= max_hours * 3600:
                delta = int(elapsed / 60)
                self._data[DATA_EINSATZ_MINUTES] = (
                    int(self._data.get(DATA_EINSATZ_MINUTES, 0)) + delta
                )
                _LOGGER.info("Einsatz: added %d min (total: %d min)", delta, self._data[DATA_EINSATZ_MINUTES])
                self._maybe_notify(
                    "🚒 Einsatz beendet",
                    f"{delta / 60:.1f}h addiert – Gesamt: {self._data[DATA_EINSATZ_MINUTES] / 60:.1f}h"
                )
            self._data[DATA_EINSATZ_STARTED] = None

        # --- Probe (absence tracking) ---
        probe_weekday = self.get_cfg(CONF_PROBE_WEEKDAY, "tue")
        probe_start = self.get_cfg(CONF_PROBE_START, "17:00")
        probe_end = self.get_cfg(CONF_PROBE_END, "23:59")
        probe_started = self._data.get(DATA_PROBE_STARTED)

        if (
            probe_started
            and _is_probe_weekday(now, probe_weekday)
            and _in_time_window(now, probe_start, probe_end)
        ):
            # Only count if timestamp is from today
            started_dt = datetime.fromtimestamp(probe_started, tz=now.tzinfo)
            if started_dt.date() == now.date():
                elapsed = now.timestamp() - probe_started
                if elapsed > 0:
                    delta = int(elapsed / 60)
                    self._data[DATA_PROBE_MINUTES] = (
                        int(self._data.get(DATA_PROBE_MINUTES, 0)) + delta
                    )
                    _LOGGER.info("Probe absence: added %d min (total: %d min)", delta, self._data[DATA_PROBE_MINUTES])
                    self._maybe_notify(
                        "🧑‍🚒 Probe beendet",
                        f"{delta / 60:.1f}h addiert – Gesamt: {self._data[DATA_PROBE_MINUTES] / 60:.1f}h"
                    )
            self._data[DATA_PROBE_STARTED] = None

        self._notify_sensors()
        self.hass.async_create_task(self._async_save())

    # ------------------------------------------------------------------
    # Per-minute tick (zone presence counting)
    # ------------------------------------------------------------------

    @callback
    def _handle_minute_tick(self, _now: datetime) -> None:
        """Every minute: if person is in zone, increment appropriate counter."""
        person = self.get_cfg(CONF_PERSON)
        zone = self._get_zone_name()
        alarm = self.get_cfg(CONF_ALARM, "")
        probe_weekday = self.get_cfg(CONF_PROBE_WEEKDAY, "tue")
        probe_count_start = self.get_cfg(CONF_PROBE_COUNT_START, "19:00")
        probe_count_end = self.get_cfg(CONF_PROBE_COUNT_END, "23:00")

        person_state = self.hass.states.get(person)
        if not person_state or person_state.state != zone:
            return

        alarm_state = self.hass.states.get(alarm)
        alarm_on = alarm_state and alarm_state.state == "on"

        now = dt_util.now()

        # Einsatz: alarm active → count as Einsatz, not Gerätehaus
        if alarm_on:
            self._data[DATA_EINSATZ_MINUTES] = int(self._data.get(DATA_EINSATZ_MINUTES, 0)) + 1
            _LOGGER.debug("Einsatz minute tick (in zone): total=%d", self._data[DATA_EINSATZ_MINUTES])
        # Probe counting: correct weekday + count window + alarm OFF
        elif (
            _is_probe_weekday(now, probe_weekday)
            and _in_time_window(now, probe_count_start, probe_count_end)
        ):
            self._data[DATA_PROBE_MINUTES] = int(self._data.get(DATA_PROBE_MINUTES, 0)) + 1
            _LOGGER.debug("Probe minute tick: total=%d", self._data[DATA_PROBE_MINUTES])
        else:
            # Gerätehaus counting
            self._data[DATA_GERATEHAUS_MINUTES] = int(self._data.get(DATA_GERATEHAUS_MINUTES, 0)) + 1
            _LOGGER.debug("Gerätehaus minute tick: total=%d", self._data[DATA_GERATEHAUS_MINUTES])

        self._notify_sensors()
        self.hass.async_create_task(self._async_save())

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def reset_category(self, category: str) -> None:
        """Reset a category to 0 minutes."""
        key_map = {
            "einsatz": DATA_EINSATZ_MINUTES,
            "probe": DATA_PROBE_MINUTES,
            "geratehaus": DATA_GERATEHAUS_MINUTES,
            "all": None,
        }
        if category == "all":
            self._data[DATA_EINSATZ_MINUTES] = 0
            self._data[DATA_PROBE_MINUTES] = 0
            self._data[DATA_GERATEHAUS_MINUTES] = 0
        elif category in key_map:
            self._data[key_map[category]] = 0

        self._notify_sensors()
        self.hass.async_create_task(self._async_save())
        _LOGGER.info("Reset category: %s", category)

    def add_minutes(self, category: str, minutes: int) -> None:
        """Manually add or subtract minutes from a category."""
        key_map = {
            "einsatz": DATA_EINSATZ_MINUTES,
            "probe": DATA_PROBE_MINUTES,
            "geratehaus": DATA_GERATEHAUS_MINUTES,
        }
        if category in key_map:
            current = int(self._data.get(key_map[category], 0))
            self._data[key_map[category]] = max(0, current + minutes)
            self._notify_sensors()
            self.hass.async_create_task(self._async_save())
            _LOGGER.info("Added %d min to %s", minutes, category)

    # ------------------------------------------------------------------
    # Sensor listener registration
    # ------------------------------------------------------------------

    def register_sensor(self, cb: callback) -> None:
        self._listeners.append(cb)

    def unregister_sensor(self, cb: callback) -> None:
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _notify_sensors(self) -> None:
        for cb in self._listeners:
            cb()

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _maybe_notify(self, title: str, message: str) -> None:
        notify_service = self.get_cfg(CONF_NOTIFY_SERVICE, "")
        if not notify_service:
            return
        self.hass.async_create_task(
            self.hass.services.async_call(
                "notify",
                notify_service.replace("notify.", ""),
                {"title": title, "message": message},
            )
        )

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def _async_save(self) -> None:
        await self._store.async_save(self._data)
