"""Tests for FeuerwehrCoordinator behavior."""
from datetime import datetime
from unittest.mock import patch

import pytest
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.storage import Store

from custom_components.feuerwehr_time_tracker.const import (
    CONF_ALARM,
    CONF_EINSATZ_MAX_HOURS,
    CONF_NOTIFY_SERVICE,
    CONF_PERSON,
    CONF_PROBE_CALENDAR,
    CONF_PROBE_KEYWORDS,
    CONF_PROBE_MAX_HOURS,
    CONF_PROBE_MODE,
    CONF_SONSTIGES_MAX_HOURS,
    CONF_TRACK_OTHER_ABSENCE,
    CONF_ZONE,
    CATEGORY_LABELS,
    DATA_CURRENT_YEAR,
    DATA_EINSATZ_MINUTES,
    DATA_EINSATZ_STARTED,
    DATA_PENDING_UNDOS,
    DATA_PREVIOUS_YEARS,
    DATA_PROBE_MINUTES,
    DATA_PROBE_STARTED,
    DATA_SONSTIGES_MINUTES,
    DATA_SONSTIGES_STARTED,
    MAX_PENDING_UNDOS,
    NOTIFY_TAG_PREFIX,
    PROBE_MODE_CALENDAR,
    PROBE_MODE_DAY_TIME,
    STORAGE_KEY,
    STORAGE_VERSION,
    UNDO_ACTION_PREFIX,
)
from custom_components.feuerwehr_time_tracker.coordinator import FeuerwehrCoordinator

ZONE_FRIENDLY_NAME = "Geraetehaus"


@pytest.fixture
def base_config() -> dict:
    return {
        CONF_PERSON: "person.max",
        CONF_ZONE: "zone.geratehaus",
        CONF_ALARM: "binary_sensor.alarm",
        CONF_EINSATZ_MAX_HOURS: 10,
        CONF_PROBE_MODE: PROBE_MODE_DAY_TIME,
    }


def _set_in_zone(hass: HomeAssistant, config: dict, alarm_on: bool) -> None:
    hass.states.async_set(
        config[CONF_ZONE], "zoning", {"friendly_name": ZONE_FRIENDLY_NAME}
    )
    hass.states.async_set(config[CONF_PERSON], ZONE_FRIENDLY_NAME)
    hass.states.async_set(config[CONF_ALARM], "on" if alarm_on else "off")


async def test_add_minutes_increments_category(hass: HomeAssistant, base_config):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    coordinator.add_minutes("einsatz", 30)
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 30
    assert coordinator.gesamt_minutes == 30


async def test_add_minutes_cannot_go_below_zero(hass: HomeAssistant, base_config):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    coordinator.add_minutes("probe", -10)
    await hass.async_block_till_done()

    assert coordinator.probe_minutes == 0


async def test_reset_single_category(hass: HomeAssistant, base_config):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_minutes("einsatz", 20)
    coordinator.add_minutes("probe", 15)
    await hass.async_block_till_done()

    coordinator.reset_category("einsatz")
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 0
    assert coordinator.probe_minutes == 15


async def test_reset_all_categories(hass: HomeAssistant, base_config):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_minutes("einsatz", 20)
    coordinator.add_minutes("probe", 15)
    coordinator.add_minutes("sonstiges", 5)
    await hass.async_block_till_done()

    coordinator.reset_category("all")
    await hass.async_block_till_done()

    assert coordinator.gesamt_minutes == 0


async def test_minute_tick_counts_as_einsatz_when_alarm_active(
    hass: HomeAssistant, base_config
):
    _set_in_zone(hass, base_config, alarm_on=True)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 1
    assert coordinator.probe_minutes == 0
    assert coordinator.sonstiges_minutes == 0


async def test_minute_tick_counts_as_sonstiges_outside_probe_window(
    hass: HomeAssistant, base_config
):
    _set_in_zone(hass, base_config, alarm_on=False)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    # Wednesday noon: not the configured probe weekday ("tue"), no alarm.
    wednesday_noon = datetime(2026, 7, 8, 12, 0)
    with patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=wednesday_noon,
    ):
        coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    assert coordinator.sonstiges_minutes == 1
    assert coordinator.probe_minutes == 0
    assert coordinator.einsatz_minutes == 0


async def test_minute_tick_counts_as_probe_during_configured_window(
    hass: HomeAssistant, base_config
):
    _set_in_zone(hass, base_config, alarm_on=False)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    # Tuesday 20:00 is within the default probe counting window (19:00-23:00).
    tuesday_evening = datetime(2026, 7, 7, 20, 0)
    with patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=tuesday_evening,
    ):
        coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    assert coordinator.probe_minutes == 1
    assert coordinator.sonstiges_minutes == 0
    assert coordinator.einsatz_minutes == 0


async def test_minute_tick_ignores_person_outside_zone(
    hass: HomeAssistant, base_config
):
    hass.states.async_set(
        base_config[CONF_ZONE], "zoning", {"friendly_name": ZONE_FRIENDLY_NAME}
    )
    hass.states.async_set(base_config[CONF_PERSON], "not_home")
    hass.states.async_set(base_config[CONF_ALARM], "off")

    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    assert coordinator.gesamt_minutes == 0


# ----------------------------------------------------------------------
# Storage migration (geratehaus_minutes -> sonstiges_minutes)
# ----------------------------------------------------------------------


async def test_storage_migration_geratehaus_to_sonstiges(
    hass: HomeAssistant, base_config
):
    """Legacy stored data must be migrated without losing any minutes."""
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_test_entry")
    await store.async_save(
        {
            "einsatz_minutes": 60,
            "probe_minutes": 30,
            "geratehaus_minutes": 123,
            "einsatz_started": None,
            "probe_started": None,
        }
    )

    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    await coordinator.async_setup()
    try:
        assert coordinator.sonstiges_minutes == 123
        assert coordinator.einsatz_minutes == 60
        assert coordinator.probe_minutes == 30
        assert "geratehaus_minutes" not in coordinator._data

        # Migration must already be persisted
        await hass.async_block_till_done()
        stored = await store.async_load()
        assert stored[DATA_SONSTIGES_MINUTES] == 123
        assert "geratehaus_minutes" not in stored
    finally:
        await coordinator.async_shutdown()


# ----------------------------------------------------------------------
# Year rollover (archive + reset)
# ----------------------------------------------------------------------


def _set_not_home(hass: HomeAssistant, config: dict) -> None:
    hass.states.async_set(
        config[CONF_ZONE], "zoning", {"friendly_name": ZONE_FRIENDLY_NAME}
    )
    hass.states.async_set(config[CONF_PERSON], "not_home")
    hass.states.async_set(config[CONF_ALARM], "off")


async def test_first_load_sets_current_year_without_archiving(
    hass: HomeAssistant, base_config
):
    """First tick ever must only establish the baseline year, never archive."""
    _set_not_home(hass, base_config)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    now = datetime(2026, 7, 8, 12, 0)
    with patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=now,
    ):
        coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    assert coordinator._data[DATA_CURRENT_YEAR] == 2026
    assert coordinator.get_previous_years_data() == {}


async def test_year_rollover_archives_and_resets(hass: HomeAssistant, base_config):
    _set_not_home(hass, base_config)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_minutes("einsatz", 120)
    coordinator.add_minutes("probe", 90)
    coordinator.add_minutes("sonstiges", 45)
    await hass.async_block_till_done()
    coordinator._data[DATA_CURRENT_YEAR] = 2026

    new_year = datetime(2027, 1, 1, 0, 1)
    with patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=new_year,
    ):
        coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 0
    assert coordinator.probe_minutes == 0
    assert coordinator.sonstiges_minutes == 0
    assert coordinator.gesamt_minutes == 0
    assert coordinator._data[DATA_CURRENT_YEAR] == 2027

    archived = coordinator.get_previous_years_data()["2026"]
    assert archived[DATA_EINSATZ_MINUTES] == 120
    assert archived[DATA_PROBE_MINUTES] == 90
    assert archived[DATA_SONSTIGES_MINUTES] == 45


async def test_year_rollover_only_fires_once(hass: HomeAssistant, base_config):
    _set_not_home(hass, base_config)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_minutes("einsatz", 10)
    await hass.async_block_till_done()
    coordinator._data[DATA_CURRENT_YEAR] = 2026

    new_year = datetime(2027, 1, 1, 0, 1)
    with patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=new_year,
    ):
        coordinator._handle_minute_tick(None)
        await hass.async_block_till_done()
        # Second tick in the same (new) year must be a no-op
        coordinator._handle_minute_tick(None)
        await hass.async_block_till_done()

    assert coordinator.get_previous_years_data() == {
        "2026": {
            DATA_EINSATZ_MINUTES: 10,
            DATA_PROBE_MINUTES: 0,
            DATA_SONSTIGES_MINUTES: 0,
        }
    }
    assert coordinator.einsatz_minutes == 0


async def test_year_rollover_detected_while_person_absent(
    hass: HomeAssistant, base_config
):
    """Rollover must fire even when the person is not in the zone at midnight."""
    _set_not_home(hass, base_config)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_minutes("sonstiges", 200)
    await hass.async_block_till_done()
    coordinator._data[DATA_CURRENT_YEAR] = 2026

    new_year = datetime(2027, 1, 1, 0, 1)
    with patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=new_year,
    ):
        coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    assert coordinator.sonstiges_minutes == 0
    assert coordinator.get_previous_years_data()["2026"][DATA_SONSTIGES_MINUTES] == 200


async def test_year_rollover_survives_offline_gap(hass: HomeAssistant, base_config):
    """HA offline across New Year (e.g. restart on Jan 3): exactly one archive."""
    _set_not_home(hass, base_config)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_minutes("einsatz", 55)
    await hass.async_block_till_done()
    coordinator._data[DATA_CURRENT_YEAR] = 2026

    jan_third = datetime(2027, 1, 3, 9, 30)
    with patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=jan_third,
    ):
        coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    previous = coordinator.get_previous_years_data()
    assert list(previous.keys()) == ["2026"]
    assert previous["2026"][DATA_EINSATZ_MINUTES] == 55
    assert coordinator.einsatz_minutes == 0
    assert coordinator._data[DATA_CURRENT_YEAR] == 2027


async def test_upgrade_from_old_storage_does_not_archive(
    hass: HomeAssistant, base_config
):
    """Stored data without current_year (pre-feature) must not create an archive."""
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_test_entry")
    await store.async_save(
        {
            "einsatz_minutes": 300,
            "probe_minutes": 100,
            "sonstiges_minutes": 50,
            "einsatz_started": None,
            "probe_started": None,
        }
    )

    _set_not_home(hass, base_config)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    await coordinator.async_setup()
    try:
        now = datetime(2026, 7, 8, 12, 0)
        with patch(
            "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
            return_value=now,
        ):
            coordinator._handle_minute_tick(None)
        await hass.async_block_till_done()

        # Counters untouched, baseline year established, no phantom archive
        assert coordinator.einsatz_minutes == 300
        assert coordinator.get_previous_years_data() == {}
        assert coordinator._data[DATA_CURRENT_YEAR] == 2026
    finally:
        await coordinator.async_shutdown()


async def test_rollover_persists_archive_before_reset(
    hass: HomeAssistant, base_config
):
    """The archive must hit the store BEFORE the counters are zeroed."""
    _set_not_home(hass, base_config)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_minutes("einsatz", 42)
    await hass.async_block_till_done()
    coordinator._data[DATA_CURRENT_YEAR] = 2026

    saved_snapshots = []
    original_save = coordinator._store.async_save

    async def spy_save(data):
        # Deep-ish copy of the relevant fields at save time
        saved_snapshots.append(
            {
                "einsatz": data.get(DATA_EINSATZ_MINUTES),
                "previous_years": {
                    k: dict(v) for k, v in data.get(DATA_PREVIOUS_YEARS, {}).items()
                },
            }
        )
        await original_save(data)

    new_year = datetime(2027, 1, 1, 0, 1)
    with patch.object(coordinator._store, "async_save", side_effect=spy_save), patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=new_year,
    ):
        coordinator._handle_minute_tick(None)
        await hass.async_block_till_done()

    # First save: archive present AND counters still hold the old values.
    first = saved_snapshots[0]
    assert first["previous_years"]["2026"][DATA_EINSATZ_MINUTES] == 42
    assert first["einsatz"] == 42

    # Final state: counters reset.
    last = saved_snapshots[-1]
    assert last["einsatz"] == 0
    assert last["previous_years"]["2026"][DATA_EINSATZ_MINUTES] == 42


# ----------------------------------------------------------------------
# Sonstiges appointment absence (calendar, non-training events)
# ----------------------------------------------------------------------

CALENDAR_ENTITY = "calendar.feuerwehr"


@pytest.fixture
def calendar_config() -> dict:
    return {
        CONF_PERSON: "person.max",
        CONF_ZONE: "zone.geratehaus",
        CONF_ALARM: "binary_sensor.alarm",
        CONF_EINSATZ_MAX_HOURS: 10,
        CONF_PROBE_MAX_HOURS: 6,
        CONF_SONSTIGES_MAX_HOURS: 6,
        CONF_PROBE_MODE: PROBE_MODE_CALENDAR,
        CONF_PROBE_CALENDAR: CALENDAR_ENTITY,
        CONF_PROBE_KEYWORDS: "Übung,Probe",
        CONF_TRACK_OTHER_ABSENCE: True,
    }


def _set_calendar(hass: HomeAssistant, on: bool, summary: str = "") -> None:
    hass.states.async_set(
        CALENDAR_ENTITY, "on" if on else "off", {"message": summary}
    )


async def test_other_appointment_absence_tracked(hass: HomeAssistant, calendar_config):
    """Toggle on + active non-keyword event: absence counts as Sonstiges."""
    _set_calendar(hass, True, "Vorstandssitzung")
    hass.states.async_set(calendar_config[CONF_ALARM], "off")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", calendar_config)

    leave = datetime(2026, 7, 8, 18, 0)
    enter = datetime(2026, 7, 8, 19, 0)  # 1h absence
    coordinator._on_zone_leave(leave, calendar_config[CONF_ALARM])
    await hass.async_block_till_done()
    assert coordinator._data[DATA_SONSTIGES_STARTED] is not None

    coordinator._on_zone_enter(enter)
    await hass.async_block_till_done()

    assert coordinator.sonstiges_minutes == 60
    assert coordinator.probe_minutes == 0
    assert coordinator.einsatz_minutes == 0
    assert coordinator._data[DATA_SONSTIGES_STARTED] is None


async def test_other_appointment_not_tracked_when_toggle_off(
    hass: HomeAssistant, calendar_config
):
    """Toggle off: a non-keyword event must NOT start a Sonstiges absence."""
    calendar_config[CONF_TRACK_OTHER_ABSENCE] = False
    _set_calendar(hass, True, "Vorstandssitzung")
    hass.states.async_set(calendar_config[CONF_ALARM], "off")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", calendar_config)

    coordinator._on_zone_leave(datetime(2026, 7, 8, 18, 0), calendar_config[CONF_ALARM])
    await hass.async_block_till_done()
    assert coordinator._data[DATA_SONSTIGES_STARTED] is None

    coordinator._on_zone_enter(datetime(2026, 7, 8, 19, 0))
    await hass.async_block_till_done()
    assert coordinator.sonstiges_minutes == 0


async def test_keyword_event_tracked_as_probe_not_sonstiges(
    hass: HomeAssistant, calendar_config
):
    """An active keyword event is a probe – never a Sonstiges appointment."""
    _set_calendar(hass, True, "Monatsübung Atemschutz")
    hass.states.async_set(calendar_config[CONF_ALARM], "off")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", calendar_config)

    leave = datetime(2026, 7, 8, 18, 0)
    enter = datetime(2026, 7, 8, 19, 0)
    coordinator._on_zone_leave(leave, calendar_config[CONF_ALARM])
    await hass.async_block_till_done()
    assert coordinator._data[DATA_PROBE_STARTED] is not None
    assert coordinator._data[DATA_SONSTIGES_STARTED] is None

    coordinator._on_zone_enter(enter)
    await hass.async_block_till_done()

    assert coordinator.probe_minutes == 60
    assert coordinator.sonstiges_minutes == 0


async def test_other_appointment_capped_at_max(hass: HomeAssistant, calendar_config):
    """Absence longer than sonstiges_max_hours is capped, not discarded."""
    calendar_config[CONF_SONSTIGES_MAX_HOURS] = 2
    _set_calendar(hass, True, "Ganztägiger Lehrgang")
    hass.states.async_set(calendar_config[CONF_ALARM], "off")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", calendar_config)

    leave = datetime(2026, 7, 8, 8, 0)
    enter = datetime(2026, 7, 8, 12, 0)  # 4h absence, cap 2h
    coordinator._on_zone_leave(leave, calendar_config[CONF_ALARM])
    await hass.async_block_till_done()
    coordinator._on_zone_enter(enter)
    await hass.async_block_till_done()

    assert coordinator.sonstiges_minutes == 120


async def test_other_appointment_counts_overnight(
    hass: HomeAssistant, calendar_config
):
    """No day-boundary check for Sonstiges: an appointment may span midnight."""
    _set_calendar(hass, True, "Nächtlicher Bereitschaftsdienst")
    hass.states.async_set(calendar_config[CONF_ALARM], "off")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", calendar_config)

    leave = datetime(2026, 7, 8, 23, 0)
    enter = datetime(2026, 7, 9, 1, 0)  # 2h absence across midnight, cap 6h
    coordinator._on_zone_leave(leave, calendar_config[CONF_ALARM])
    await hass.async_block_till_done()
    coordinator._on_zone_enter(enter)
    await hass.async_block_till_done()

    assert coordinator.sonstiges_minutes == 120


async def test_probe_absence_capped_at_max(hass: HomeAssistant, base_config):
    """Probe absence keeps its day-boundary but is now capped at probe_max_hours."""
    base_config[CONF_PROBE_MAX_HOURS] = 2
    hass.states.async_set(base_config[CONF_ALARM], "off")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    # Tuesday, both timestamps inside the probe window (17:00-23:59), same day.
    leave = datetime(2026, 7, 7, 17, 30)
    enter = datetime(2026, 7, 7, 22, 0)  # 4.5h absence, cap 2h
    coordinator._on_zone_leave(leave, base_config[CONF_ALARM])
    await hass.async_block_till_done()
    assert coordinator._data[DATA_PROBE_STARTED] is not None

    coordinator._on_zone_enter(enter)
    await hass.async_block_till_done()

    assert coordinator.probe_minutes == 120


def _alarm_off_event(config: dict) -> Event:
    """Build a state_changed event for the alarm going on -> off."""
    alarm = config[CONF_ALARM]
    return Event(
        "state_changed",
        {
            "entity_id": alarm,
            "old_state": State(alarm, "on"),
            "new_state": State(alarm, "off"),
        },
    )


async def test_einsatz_discarded_when_alarm_off_between_alarms(
    hass: HomeAssistant, base_config
):
    """Two separate alarms must not merge: the gap in between is not Einsatz.

    Reproduces the reported bug – member leaves the station during alarm #1
    without departing, goes home, alarm #1 ends, and hours later alarm #2
    arrives and the member drives back. The ~3h gap must NOT be counted.
    """
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    # Alarm #1 active, member leaves the zone -> einsatz_started is set.
    hass.states.async_set(base_config[CONF_ALARM], "on")
    coordinator._on_zone_leave(datetime(2026, 7, 7, 17, 0), base_config[CONF_ALARM])
    await hass.async_block_till_done()
    assert coordinator._data[DATA_EINSATZ_STARTED] is not None

    # Alarm #1 ends -> the pending einsatz_started must be discarded.
    coordinator._handle_alarm_state_change(_alarm_off_event(base_config))
    await hass.async_block_till_done()
    assert coordinator._data[DATA_EINSATZ_STARTED] is None

    # Alarm #2 (~3h later), member returns to the station.
    hass.states.async_set(base_config[CONF_ALARM], "on")
    coordinator._on_zone_enter(datetime(2026, 7, 7, 20, 0))
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 0


async def test_einsatz_counted_when_alarm_stays_on(hass: HomeAssistant, base_config):
    """Regression: a genuine mission (alarm stays on) still counts normally."""
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    # Alarm active, member departs (leaves zone) and returns 2h later while the
    # alarm is still on – no alarm-off event in between.
    hass.states.async_set(base_config[CONF_ALARM], "on")
    coordinator._on_zone_leave(datetime(2026, 7, 7, 17, 0), base_config[CONF_ALARM])
    await hass.async_block_till_done()

    coordinator._on_zone_enter(datetime(2026, 7, 7, 19, 0))
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 120


async def test_alarm_off_event_ignored_without_pending_einsatz(
    hass: HomeAssistant, base_config
):
    """An alarm-off event without a pending einsatz_started is a no-op."""
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    assert coordinator._data[DATA_EINSATZ_STARTED] is None

    coordinator._handle_alarm_state_change(_alarm_off_event(base_config))
    await hass.async_block_till_done()

    assert coordinator._data[DATA_EINSATZ_STARTED] is None
    assert coordinator.einsatz_minutes == 0


# ----------------------------------------------------------------------
# Undo via actionable notification
# ----------------------------------------------------------------------


@pytest.fixture
def notify_config(base_config) -> dict:
    return {**base_config, CONF_NOTIFY_SERVICE: "notify.mobile_app_test"}


def _register_notify(hass: HomeAssistant) -> list:
    """Register a fake notify.mobile_app_test service, collecting its calls."""
    calls: list = []

    @callback
    def _record(call) -> None:
        calls.append(call)

    hass.services.async_register("notify", "mobile_app_test", _record)
    return calls


async def test_notify_with_undo_registers_record_and_action(
    hass: HomeAssistant, notify_config
):
    """A notification with an undo attaches a button and stores a pending record."""
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)

    coordinator._maybe_notify(
        "🚒 Einsatz beendet", "2.5h addiert", category="einsatz", delta_minutes=150
    )
    await hass.async_block_till_done()

    # Exactly one pending undo record, matching the notified addition.
    undos = coordinator._data[DATA_PENDING_UNDOS]
    assert len(undos) == 1
    token, record = next(iter(undos.items()))
    assert record["category"] == "einsatz"
    assert record["minutes"] == 150

    # The notification payload carries the undo action + a per-token tag.
    payload = calls[-1].data
    action = payload["data"]["actions"][0]
    assert action["action"] == f"{UNDO_ACTION_PREFIX}{token}"
    assert action["title"] == "2.5h zurücksetzen"
    assert payload["data"]["tag"] == f"{NOTIFY_TAG_PREFIX}{token}"


async def test_maybe_notify_without_service_stores_no_undo(
    hass: HomeAssistant, base_config
):
    """No notify service configured → no notification and no pending undo."""
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    coordinator._maybe_notify("t", "m", category="einsatz", delta_minutes=60)
    await hass.async_block_till_done()

    assert coordinator._data[DATA_PENDING_UNDOS] == {}


async def test_try_undo_subtracts_correct_minutes_for_matching_token(
    hass: HomeAssistant, notify_config
):
    """With multiple pending undos, only the tapped token's value is reset."""
    _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)
    coordinator.add_minutes("einsatz", 100)
    coordinator.add_minutes("probe", 50)
    coordinator._data[DATA_PENDING_UNDOS] = {
        "TOK_EINSATZ": {"category": "einsatz", "minutes": 60, "created": 1.0},
        "TOK_PROBE": {"category": "probe", "minutes": 30, "created": 2.0},
    }
    await hass.async_block_till_done()

    # Lower-case lookup must still match (iOS uppercases action identifiers).
    assert coordinator.try_undo("tok_einsatz") is True
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 40  # 100 - 60
    assert coordinator.probe_minutes == 50    # untouched
    # Used token gone, the other one still pending.
    assert "TOK_EINSATZ" not in coordinator._data[DATA_PENDING_UNDOS]
    assert "TOK_PROBE" in coordinator._data[DATA_PENDING_UNDOS]


async def test_try_undo_unknown_token_is_noop(hass: HomeAssistant, notify_config):
    """An unknown/already-used token returns False and changes nothing."""
    _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)
    coordinator.add_minutes("einsatz", 100)
    await hass.async_block_till_done()

    assert coordinator.try_undo("does_not_exist") is False
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 100


async def test_try_undo_clamps_at_zero(hass: HomeAssistant, notify_config):
    """Undoing more than the current total clamps the counter at 0."""
    _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)
    coordinator.add_minutes("probe", 20)
    coordinator._data[DATA_PENDING_UNDOS] = {
        "T": {"category": "probe", "minutes": 60, "created": 1.0}
    }
    await hass.async_block_till_done()

    assert coordinator.try_undo("T") is True
    await hass.async_block_till_done()

    assert coordinator.probe_minutes == 0


async def test_try_undo_clears_original_and_sends_fresh_confirmation(
    hass: HomeAssistant, notify_config
):
    """Undo clears the original notification and sends a fresh confirmation.

    The confirmation uses its OWN tag (not the original's, which iOS already
    dismissed on tap) and carries no undo button.
    """
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)
    coordinator.add_minutes("sonstiges", 90)
    coordinator._data[DATA_PENDING_UNDOS] = {
        "ABC": {"category": "sonstiges", "minutes": 30, "created": 1.0}
    }
    await hass.async_block_till_done()

    coordinator.try_undo("ABC")
    await hass.async_block_till_done()

    # The original notification is cleared by its tag.
    clear_calls = [
        c for c in calls if c.data.get("message") == "clear_notification"
    ]
    assert any(
        c.data["data"]["tag"] == f"{NOTIFY_TAG_PREFIX}ABC" for c in clear_calls
    )

    # The confirmation is a fresh push with its own tag and no undo action.
    confirmations = [
        c for c in calls if c.data.get("title") == "↩️ Zurückgesetzt"
    ]
    assert len(confirmations) == 1
    payload = confirmations[0].data
    assert payload["data"]["tag"] == f"{NOTIFY_TAG_PREFIX}done_ABC"
    assert "actions" not in payload["data"]
    assert CATEGORY_LABELS["sonstiges"] in payload["message"]


async def test_prune_pending_undos_caps_at_max(hass: HomeAssistant, notify_config):
    """Beyond the cap, the oldest records (smallest 'created') are dropped."""
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)
    coordinator._data[DATA_PENDING_UNDOS] = {
        f"t{i}": {"category": "einsatz", "minutes": 1, "created": float(i)}
        for i in range(MAX_PENDING_UNDOS + 5)
    }

    coordinator._prune_pending_undos()

    undos = coordinator._data[DATA_PENDING_UNDOS]
    assert len(undos) == MAX_PENDING_UNDOS
    # The 5 oldest (created 0..4) were removed, the newest survive.
    assert "t0" not in undos
    assert "t4" not in undos
    assert f"t{MAX_PENDING_UNDOS + 4}" in undos


async def test_einsatz_notification_undo_end_to_end(
    hass: HomeAssistant, notify_config
):
    """Full path: an einsatz addition can be fully undone via its token."""
    _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)

    hass.states.async_set(notify_config[CONF_ALARM], "on")
    coordinator._on_zone_leave(datetime(2026, 7, 7, 17, 0), notify_config[CONF_ALARM])
    await hass.async_block_till_done()
    coordinator._on_zone_enter(datetime(2026, 7, 7, 19, 0))  # 2h absence
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 120
    undos = coordinator._data[DATA_PENDING_UNDOS]
    assert len(undos) == 1
    token = next(iter(undos))

    assert coordinator.try_undo(token) is True
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 0
    assert coordinator._data[DATA_PENDING_UNDOS] == {}


async def test_small_duration_undo_uses_actual_minutes_not_rounded_hours(
    hass: HomeAssistant, notify_config
):
    """A 2-minute addition shows '2 min' and undoes the real 2 minutes (not 0.0h)."""
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)
    coordinator.add_minutes("einsatz", 2)

    coordinator._maybe_notify(
        "🚒 Einsatz beendet", "kurz", category="einsatz", delta_minutes=2
    )
    await hass.async_block_till_done()

    # Button reads minutes, not "0.0h"; the record keeps the exact minutes.
    token, record = next(iter(coordinator._data[DATA_PENDING_UNDOS].items()))
    assert record["minutes"] == 2
    assert calls[-1].data["data"]["actions"][0]["title"] == "2 min zurücksetzen"

    assert coordinator.try_undo(token) is True
    await hass.async_block_till_done()

    # The real 2 minutes were subtracted, not a rounded 0.
    assert coordinator.einsatz_minutes == 0
