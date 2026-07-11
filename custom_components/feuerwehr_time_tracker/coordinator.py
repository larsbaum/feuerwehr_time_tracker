"""Coordinator for Feuerwehr Zeit-Tracker – handles all tracking logic."""
from __future__ import annotations

import asyncio
import logging
import secrets
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
    CONF_PROBE_MODE,
    CONF_PROBE_WEEKDAY,
    CONF_PROBE_START,
    CONF_PROBE_END,
    CONF_PROBE_COUNT_START,
    CONF_PROBE_COUNT_END,
    CONF_PROBE_CALENDAR,
    CONF_PROBE_KEYWORDS,
    CONF_EINSATZ_MAX_HOURS,
    CONF_PROBE_MAX_HOURS,
    CONF_TRACK_OTHER_ABSENCE,
    CONF_SONSTIGES_MAX_HOURS,
    CONF_NOTIFY_SERVICE,
    DATA_EINSATZ_MINUTES,
    DATA_PROBE_MINUTES,
    DATA_SONSTIGES_MINUTES,
    DATA_EINSATZ_STARTED,
    DATA_PROBE_STARTED,
    DATA_SONSTIGES_STARTED,
    DATA_CURRENT_YEAR,
    DATA_PREVIOUS_YEARS,
    DATA_PENDING_UNDOS,
    MAX_PENDING_UNDOS,
    UNDO_ACTION_PREFIX,
    NOTIFY_TAG_PREFIX,
    CATEGORY_LABELS,
    LEGACY_DATA_GERATEHAUS_MINUTES,
    PROBE_MODE_DAY_TIME,
    PROBE_MODE_CALENDAR,
    PROBE_MODE_BOTH,
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
            DATA_SONSTIGES_MINUTES: 0,
            DATA_EINSATZ_STARTED: None,
            DATA_PROBE_STARTED: None,
            DATA_SONSTIGES_STARTED: None,
            DATA_CURRENT_YEAR: None,
            DATA_PREVIOUS_YEARS: {},
            DATA_PENDING_UNDOS: {},
        }

        self._unsub_zone = None
        self._unsub_timer = None
        self._unsub_alarm = None
        self._listeners: list[callback] = []
        self._rollover_in_progress = False

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
    def sonstiges_minutes(self) -> int:
        return int(self._data.get(DATA_SONSTIGES_MINUTES, 0))

    @property
    def gesamt_minutes(self) -> int:
        return self.einsatz_minutes + self.probe_minutes + self.sonstiges_minutes

    def get_previous_years_data(self) -> dict[str, dict[str, int]]:
        """Return a copy of the archived per-year totals."""
        return dict(self._data.get(DATA_PREVIOUS_YEARS, {}))

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
    # Calendar-based probe check
    # ------------------------------------------------------------------

    def _is_probe_calendar_active(self) -> bool:
        """Check if a matching calendar event is currently active."""
        cal_entity = self.get_cfg(CONF_PROBE_CALENDAR, "")
        if not cal_entity:
            return False

        cal_state = self.hass.states.get(cal_entity)
        if not cal_state or cal_state.state != "on":
            return False

        # Check keywords against the event summary/message
        keywords_raw = self.get_cfg(CONF_PROBE_KEYWORDS, "")
        if not keywords_raw:
            # No keywords configured → any active event counts
            return True

        keywords = [kw.strip().lower() for kw in keywords_raw.split(",") if kw.strip()]
        if not keywords:
            return True

        # Calendar entities expose the current event title as 'message' attribute
        event_summary = (cal_state.attributes.get("message") or "").lower()

        return any(kw in event_summary for kw in keywords)

    def _is_other_appointment_active(self) -> bool:
        """Check if a non-training calendar event is currently active.

        Used to track appointments outside the fire station that are NOT
        exercises (e.g. meetings, courses) as "Sonstiges" absence – only when
        the toggle is enabled.  A configured calendar is mandatory so that
        arbitrary zone exits (shopping etc.) never count: only a running
        calendar event whose title does NOT match any of the probe keywords
        qualifies.  Without keywords every active event is a probe, so there is
        nothing "other" to track (no double counting).
        """
        if not self.get_cfg(CONF_TRACK_OTHER_ABSENCE, False):
            return False

        cal_entity = self.get_cfg(CONF_PROBE_CALENDAR, "")
        if not cal_entity:
            return False

        cal_state = self.hass.states.get(cal_entity)
        if not cal_state or cal_state.state != "on":
            return False

        keywords_raw = self.get_cfg(CONF_PROBE_KEYWORDS, "")
        keywords = [kw.strip().lower() for kw in keywords_raw.split(",") if kw.strip()]
        if not keywords:
            return False

        event_summary = (cal_state.attributes.get("message") or "").lower()
        # "Other" = active event that is NOT a training (no keyword match).
        return not any(kw in event_summary for kw in keywords)

    def _is_day_time_probe_active(self, now: datetime) -> bool:
        """Check if day & time based probe window is active."""
        probe_weekday = self.get_cfg(CONF_PROBE_WEEKDAY, "tue")
        probe_start = self.get_cfg(CONF_PROBE_START, "17:00")
        probe_end = self.get_cfg(CONF_PROBE_END, "23:59")
        return _is_probe_weekday(now, probe_weekday) and _in_time_window(now, probe_start, probe_end)

    def _is_day_time_probe_count_active(self, now: datetime) -> bool:
        """Check if day & time based probe counting window is active."""
        probe_weekday = self.get_cfg(CONF_PROBE_WEEKDAY, "tue")
        probe_count_start = self.get_cfg(CONF_PROBE_COUNT_START, "19:00")
        probe_count_end = self.get_cfg(CONF_PROBE_COUNT_END, "23:00")
        return _is_probe_weekday(now, probe_weekday) and _in_time_window(now, probe_count_start, probe_count_end)

    def _is_probe_active(self, now: datetime) -> bool:
        """Check if probe tracking should be active based on configured mode."""
        mode = self.get_cfg(CONF_PROBE_MODE, PROBE_MODE_DAY_TIME)

        if mode == PROBE_MODE_DAY_TIME:
            return self._is_day_time_probe_active(now)
        elif mode == PROBE_MODE_CALENDAR:
            return self._is_probe_calendar_active()
        else:  # BOTH – either condition triggers probe
            return self._is_day_time_probe_active(now) or self._is_probe_calendar_active()

    def _is_probe_count_active(self, now: datetime) -> bool:
        """Check if probe minute counting (in-zone) should be active."""
        mode = self.get_cfg(CONF_PROBE_MODE, PROBE_MODE_DAY_TIME)

        if mode == PROBE_MODE_DAY_TIME:
            return self._is_day_time_probe_count_active(now)
        elif mode == PROBE_MODE_CALENDAR:
            return self._is_probe_calendar_active()
        else:  # BOTH – either condition triggers counting
            return self._is_day_time_probe_count_active(now) or self._is_probe_calendar_active()

    # ------------------------------------------------------------------
    # Setup / Teardown
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Load stored data and start listeners."""
        stored = await self._store.async_load()
        if stored:
            self._data.update(stored)
            _LOGGER.debug("Loaded stored data: %s", self._data)

        # Migration: rename legacy "geratehaus_minutes" key to "sonstiges_minutes".
        # Idempotent – after the first run the legacy key is gone from the store.
        if LEGACY_DATA_GERATEHAUS_MINUTES in self._data:
            legacy_minutes = int(self._data.pop(LEGACY_DATA_GERATEHAUS_MINUTES) or 0)
            if int(self._data.get(DATA_SONSTIGES_MINUTES, 0)) == 0:
                self._data[DATA_SONSTIGES_MINUTES] = legacy_minutes
            await self._store.async_save(self._data)
            _LOGGER.info(
                "Migrated stored minutes: geratehaus_minutes -> sonstiges_minutes (%d min)",
                self._data[DATA_SONSTIGES_MINUTES],
            )

        person = self.get_cfg(CONF_PERSON)

        self._unsub_zone = async_track_state_change_event(
            self.hass, [person], self._handle_person_state_change
        )
        self._unsub_timer = async_track_time_interval(
            self.hass, self._handle_minute_tick, timedelta(minutes=1)
        )

        # Listen for the alarm sensor leaving the "on" state. This lets us
        # discard a pending einsatz_started as soon as the triggering alarm
        # ends – so a later, unrelated alarm can't retroactively count the gap
        # in between as Einsatz (see _handle_alarm_state_change).
        alarm = self.get_cfg(CONF_ALARM)
        if alarm:
            self._unsub_alarm = async_track_state_change_event(
                self.hass, [alarm], self._handle_alarm_state_change
            )
        _LOGGER.info("Feuerwehr Zeit-Tracker coordinator started for %s", person)

    async def async_shutdown(self) -> None:
        """Stop all listeners."""
        if self._unsub_zone:
            self._unsub_zone()
        if self._unsub_timer:
            self._unsub_timer()
        if self._unsub_alarm:
            self._unsub_alarm()
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

    @callback
    def _handle_alarm_state_change(self, event: Event) -> None:
        """Discard a pending einsatz_started once the alarm leaves 'on'.

        Scenario this guards against: a member drives to the station during an
        alarm and leaves the zone again without departing (einsatz_started is
        set). That alarm ends, and hours later a *different* alarm arrives for
        which the member returns to the station. Without this handler the
        stale einsatz_started would survive and _on_zone_enter would count the
        whole gap in between (~3h in the reported case) as Einsatz.

        Any state other than 'on' (including 'off'/'unavailable'/'unknown')
        counts as "the alarm was off in between", mirroring the alarm_on
        definition used elsewhere. A genuine mission keeps the alarm 'on'
        throughout, so this handler never fires for it.
        """
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state == "on":
            return
        if self._data.get(DATA_EINSATZ_STARTED) is not None:
            _LOGGER.info(
                "Alarm no longer active (%s) – discarding pending einsatz_started",
                new_state.state,
            )
            self._data[DATA_EINSATZ_STARTED] = None
            self.hass.async_create_task(self._async_save())

    def _on_zone_leave(self, now: datetime, alarm_entity: str) -> None:
        """Handle zone leave: set start timestamps if conditions match."""
        alarm_state = self.hass.states.get(alarm_entity)
        alarm_on = alarm_state and alarm_state.state == "on"

        # Priority: Einsatz (alarm) > Probe > sonstiger Termin (calendar).
        # Mutually exclusive: in calendar mode _is_probe_active already checks
        # the keyword match, so a keyword event is a probe and a non-keyword
        # event is "other" – never both.
        if alarm_on:
            self._data[DATA_EINSATZ_STARTED] = now.timestamp()
            _LOGGER.info("Einsatz started at %s", now)
        elif self._is_probe_active(now):
            self._data[DATA_PROBE_STARTED] = now.timestamp()
            _LOGGER.info("Probe absence started at %s", now)
        elif self._is_other_appointment_active():
            self._data[DATA_SONSTIGES_STARTED] = now.timestamp()
            _LOGGER.info("Sonstiges appointment absence started at %s", now)

        self.hass.async_create_task(self._async_save())

    def _on_zone_enter(self, now: datetime) -> None:
        """Handle zone enter: calculate and add minutes if applicable."""
        einsatz_max = self.get_cfg(CONF_EINSATZ_MAX_HOURS, 10)
        probe_max = self.get_cfg(CONF_PROBE_MAX_HOURS, 6)
        sonstiges_max = self.get_cfg(CONF_SONSTIGES_MAX_HOURS, 6)
        alarm_entity = self.get_cfg(CONF_ALARM, "")
        alarm_state = self.hass.states.get(alarm_entity)
        alarm_on = alarm_state and alarm_state.state == "on"

        # --- Einsatz ---
        einsatz_started = self._data.get(DATA_EINSATZ_STARTED)
        if einsatz_started:
            if alarm_on:
                # Alarm still active → add elapsed minutes
                elapsed = now.timestamp() - einsatz_started
                if 0 < elapsed <= einsatz_max * 3600:
                    delta = int(elapsed / 60)
                    self._data[DATA_EINSATZ_MINUTES] = (
                        int(self._data.get(DATA_EINSATZ_MINUTES, 0)) + delta
                    )
                    _LOGGER.info("Einsatz: added %d min (total: %d min)", delta, self._data[DATA_EINSATZ_MINUTES])
                    self._maybe_notify(
                        "🚒 Einsatz beendet",
                        f"{delta / 60:.1f}h addiert – Gesamt: {self._data[DATA_EINSATZ_MINUTES] / 60:.1f}h",
                        category="einsatz",
                        delta_minutes=delta,
                    )
            else:
                _LOGGER.info("Einsatz: alarm no longer active, discarding %d sec absence",
                             int(now.timestamp() - einsatz_started))
            self._data[DATA_EINSATZ_STARTED] = None

        # --- Probe (absence tracking) ---
        probe_started = self._data.get(DATA_PROBE_STARTED)

        if probe_started and self._is_probe_active(now):
            # Only count if timestamp is from today (day-boundary protection –
            # a probe must not run over night).
            started_dt = datetime.fromtimestamp(probe_started, tz=now.tzinfo)
            if started_dt.date() == now.date():
                elapsed = now.timestamp() - probe_started
                if elapsed > 0:
                    # Cap (not discard) the absence at probe_max hours.
                    delta = int(min(elapsed, probe_max * 3600) / 60)
                    self._data[DATA_PROBE_MINUTES] = (
                        int(self._data.get(DATA_PROBE_MINUTES, 0)) + delta
                    )
                    _LOGGER.info("Probe absence: added %d min (total: %d min)", delta, self._data[DATA_PROBE_MINUTES])
                    self._maybe_notify(
                        "🧑‍🚒 Probe beendet",
                        f"{delta / 60:.1f}h addiert – Gesamt: {self._data[DATA_PROBE_MINUTES] / 60:.1f}h",
                        category="probe",
                        delta_minutes=delta,
                    )
            self._data[DATA_PROBE_STARTED] = None

        # --- Sonstiges (appointment absence tracking) ---
        sonstiges_started = self._data.get(DATA_SONSTIGES_STARTED)
        if sonstiges_started:
            # NO day-boundary check: an appointment may run past midnight.
            # The only limit is the sonstiges_max hours cap. The event no
            # longer needs to be active on return (appointments end).
            elapsed = now.timestamp() - sonstiges_started
            if elapsed > 0:
                # Cap (not discard) the absence at sonstiges_max hours.
                delta = int(min(elapsed, sonstiges_max * 3600) / 60)
                self._data[DATA_SONSTIGES_MINUTES] = (
                    int(self._data.get(DATA_SONSTIGES_MINUTES, 0)) + delta
                )
                _LOGGER.info("Sonstiges appointment: added %d min (total: %d min)", delta, self._data[DATA_SONSTIGES_MINUTES])
                self._maybe_notify(
                    "🧰 Termin beendet",
                    f"{delta / 60:.1f}h addiert – Gesamt: {self._data[DATA_SONSTIGES_MINUTES] / 60:.1f}h",
                    category="sonstiges",
                    delta_minutes=delta,
                )
            self._data[DATA_SONSTIGES_STARTED] = None

        self._notify_sensors()
        self.hass.async_create_task(self._async_save())

    # ------------------------------------------------------------------
    # Per-minute tick (zone presence counting)
    # ------------------------------------------------------------------

    @callback
    def _handle_minute_tick(self, _now: datetime) -> None:
        """Every minute: if person is in zone, increment appropriate counter."""
        now = dt_util.now()

        # Year rollover must be checked unconditionally – BEFORE the presence
        # early-return below. Otherwise the reset would fire hours late (only
        # once the person re-enters the zone) and new-year minutes would leak
        # into the archived previous-year totals.
        self._check_year_rollover(now)

        person = self.get_cfg(CONF_PERSON)
        zone = self._get_zone_name()
        alarm = self.get_cfg(CONF_ALARM, "")

        person_state = self.hass.states.get(person)
        if not person_state or person_state.state != zone:
            return

        alarm_state = self.hass.states.get(alarm)
        alarm_on = alarm_state and alarm_state.state == "on"

        # Einsatz: alarm active → count as Einsatz, not Sonstiges
        if alarm_on:
            self._data[DATA_EINSATZ_MINUTES] = int(self._data.get(DATA_EINSATZ_MINUTES, 0)) + 1
            _LOGGER.debug("Einsatz minute tick (in zone): total=%d", self._data[DATA_EINSATZ_MINUTES])
        # Probe counting: check based on configured mode
        elif self._is_probe_count_active(now):
            self._data[DATA_PROBE_MINUTES] = int(self._data.get(DATA_PROBE_MINUTES, 0)) + 1
            _LOGGER.debug("Probe minute tick: total=%d", self._data[DATA_PROBE_MINUTES])
        else:
            # Sonstiges counting
            self._data[DATA_SONSTIGES_MINUTES] = int(self._data.get(DATA_SONSTIGES_MINUTES, 0)) + 1
            _LOGGER.debug("Sonstiges minute tick: total=%d", self._data[DATA_SONSTIGES_MINUTES])

        self._notify_sensors()
        self.hass.async_create_task(self._async_save())

    # ------------------------------------------------------------------
    # Year rollover (archive + reset)
    # ------------------------------------------------------------------

    @callback
    def _check_year_rollover(self, now: datetime) -> None:
        """Detect a year change and trigger archive + reset exactly once."""
        if self._rollover_in_progress:
            return

        stored_year = self._data.get(DATA_CURRENT_YEAR)

        if stored_year is None:
            # First load ever (fresh install or upgrade from a version without
            # year tracking): establish the baseline year WITHOUT archiving –
            # there is no completed previous year to archive yet.
            self._data[DATA_CURRENT_YEAR] = now.year
            self.hass.async_create_task(self._async_save())
            return

        if now.year == stored_year:
            return

        self._rollover_in_progress = True
        self.hass.async_create_task(
            self._async_perform_rollover(int(stored_year), now.year)
        )

    async def _async_perform_rollover(self, old_year: int, new_year: int) -> None:
        """Archive the finished year's totals, then reset the counters.

        Ordering is crash-safe: the archive is persisted to the store FIRST
        (while the counters still hold their old values). Only after that
        save succeeds are the counters zeroed and saved again. If HA dies
        in between, the next startup re-runs the rollover idempotently –
        no minutes are ever lost.
        """
        try:
            # Step 1: archive in memory (counters untouched).
            previous_years = dict(self._data.get(DATA_PREVIOUS_YEARS, {}))
            previous_years[str(old_year)] = {
                DATA_EINSATZ_MINUTES: self.einsatz_minutes,
                DATA_PROBE_MINUTES: self.probe_minutes,
                DATA_SONSTIGES_MINUTES: self.sonstiges_minutes,
            }
            self._data[DATA_PREVIOUS_YEARS] = previous_years

            # Step 2: persist the archive BEFORE touching the counters.
            await self._store.async_save(self._data)

            # Step 3: now it is safe to reset (gesamt is computed → follows).
            self._data[DATA_EINSATZ_MINUTES] = 0
            self._data[DATA_PROBE_MINUTES] = 0
            self._data[DATA_SONSTIGES_MINUTES] = 0
            self._data[DATA_CURRENT_YEAR] = new_year

            # Step 4: push to sensors and persist the reset state.
            self._notify_sensors()
            await self._store.async_save(self._data)
            _LOGGER.info(
                "Year rollover: archived %d, counters reset for %d", old_year, new_year
            )
        finally:
            self._rollover_in_progress = False

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def reset_category(self, category: str) -> None:
        """Reset a category to 0 minutes."""
        key_map = {
            "einsatz": DATA_EINSATZ_MINUTES,
            "probe": DATA_PROBE_MINUTES,
            "sonstiges": DATA_SONSTIGES_MINUTES,
            "all": None,
        }
        if category == "all":
            self._data[DATA_EINSATZ_MINUTES] = 0
            self._data[DATA_PROBE_MINUTES] = 0
            self._data[DATA_SONSTIGES_MINUTES] = 0
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
            "sonstiges": DATA_SONSTIGES_MINUTES,
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

    def _maybe_notify(
        self,
        title: str,
        message: str,
        category: str | None = None,
        delta_minutes: int = 0,
    ) -> None:
        """Send a push notification, optionally with an "undo" action button.

        When ``category`` and a positive ``delta_minutes`` are given, a unique
        undo token is registered and an actionable-notification button
        ("X.Xh zurücksetzen") is attached. Tapping it later fires an event that
        routes back to :meth:`try_undo` (see __init__._handle_notification_action).
        """
        notify_service = self.get_cfg(CONF_NOTIFY_SERVICE, "")
        if not notify_service:
            return

        payload: dict[str, Any] = {"title": title, "message": message}

        if category and delta_minutes > 0:
            token = secrets.token_hex(4)
            self._data.setdefault(DATA_PENDING_UNDOS, {})[token] = {
                "category": category,
                "minutes": int(delta_minutes),
                "created": dt_util.now().timestamp(),
            }
            self._prune_pending_undos()
            payload["data"] = {
                "tag": f"{NOTIFY_TAG_PREFIX}{token}",
                "actions": [
                    {
                        "action": f"{UNDO_ACTION_PREFIX}{token}",
                        "title": f"{delta_minutes / 60:.1f}h zurücksetzen",
                        "destructive": True,
                    }
                ],
            }
            self.hass.async_create_task(self._async_save())

        self.hass.async_create_task(
            self.hass.services.async_call(
                "notify",
                notify_service.replace("notify.", ""),
                payload,
            )
        )

    def _prune_pending_undos(self) -> None:
        """Keep only the newest MAX_PENDING_UNDOS records (no time expiry)."""
        undos = self._data.get(DATA_PENDING_UNDOS, {})
        if len(undos) <= MAX_PENDING_UNDOS:
            return
        # Drop the oldest records first (smallest "created" timestamp).
        ordered = sorted(undos.items(), key=lambda kv: kv[1].get("created", 0))
        for token, _rec in ordered[: len(undos) - MAX_PENDING_UNDOS]:
            undos.pop(token, None)

    def try_undo(self, token: str) -> bool:
        """Undo a previously notified time addition, identified by ``token``.

        Returns True if the token matched a pending undo record (and the minutes
        were subtracted), False otherwise. Idempotent: a second tap on the same
        notification finds no record and is a no-op.
        """
        record = self._data.get(DATA_PENDING_UNDOS, {}).pop(token, None)
        if record is None:
            return False

        category = record["category"]
        minutes = int(record["minutes"])
        # add_minutes clamps at 0, notifies sensors and saves _data (which no
        # longer contains the popped token).
        self.add_minutes(category, -minutes)

        new_total = int(self._data.get(f"{category}_minutes", 0))
        label = CATEGORY_LABELS.get(category, category)
        # Reuse the original notification's tag so this confirmation REPLACES the
        # original push in place (removes the undo button, shows the result).
        self._notify_raw(
            "↩️ Zurückgesetzt",
            f"{label}: {minutes / 60:.1f}h zurückgesetzt – neuer Stand: {new_total / 60:.1f}h",
            tag=f"{NOTIFY_TAG_PREFIX}{token}",
        )
        _LOGGER.info("Undo %s: removed %d min via token %s", category, minutes, token)
        return True

    def _notify_raw(self, title: str, message: str, tag: str | None = None) -> None:
        """Send a plain push notification (no undo action)."""
        notify_service = self.get_cfg(CONF_NOTIFY_SERVICE, "")
        if not notify_service:
            return
        payload: dict[str, Any] = {"title": title, "message": message}
        if tag:
            payload["data"] = {"tag": tag}
        self.hass.async_create_task(
            self.hass.services.async_call(
                "notify",
                notify_service.replace("notify.", ""),
                payload,
            )
        )

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def _async_save(self) -> None:
        await self._store.async_save(self._data)
