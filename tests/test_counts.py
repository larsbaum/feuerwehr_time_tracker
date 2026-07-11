"""Tests for mission-count tracking (Einsatzzahlen)."""
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
    CONF_PROBE_MODE,
    CONF_ZONE,
    DATA_ALARM_AT_STATION,
    DATA_ALARM_RESPONDED,
    DATA_COUNT_RESPONDED,
    DATA_COUNT_STANDBY,
    DATA_COUNT_TOTAL,
    DATA_CURRENT_YEAR,
    DATA_PENDING_UNDOS,
    DATA_PREVIOUS_YEARS,
    NOTIFY_TAG_PREFIX,
    PROBE_MODE_DAY_TIME,
    STORAGE_KEY,
    STORAGE_VERSION,
    UNDO_TYPE_COUNT,
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


@pytest.fixture
def notify_config(base_config) -> dict:
    return {**base_config, CONF_NOTIFY_SERVICE: "notify.mobile_app_test"}


def _set_zone(hass: HomeAssistant, config: dict) -> None:
    hass.states.async_set(
        config[CONF_ZONE], "zoning", {"friendly_name": ZONE_FRIENDLY_NAME}
    )


def _set_person_in_zone(hass: HomeAssistant, config: dict) -> None:
    _set_zone(hass, config)
    hass.states.async_set(config[CONF_PERSON], ZONE_FRIENDLY_NAME)


def _set_person_away(hass: HomeAssistant, config: dict) -> None:
    _set_zone(hass, config)
    hass.states.async_set(config[CONF_PERSON], "not_home")


def _alarm_event(config: dict, old: str | None, new: str | None) -> Event:
    """Build a state_changed event for the alarm sensor."""
    alarm = config[CONF_ALARM]
    return Event(
        "state_changed",
        {
            "entity_id": alarm,
            "old_state": State(alarm, old) if old is not None else None,
            "new_state": State(alarm, new) if new is not None else None,
        },
    )


def _register_notify(hass: HomeAssistant) -> list:
    calls: list = []

    @callback
    def _record(call) -> None:
        calls.append(call)

    hass.services.async_register("notify", "mobile_app_test", _record)
    return calls


# ----------------------------------------------------------------------
# Classification on alarm on -> off
# ----------------------------------------------------------------------


async def test_alarm_off_counts_total_only_when_not_involved(
    hass: HomeAssistant, base_config
):
    """An alarm the member had nothing to do with only bumps the total."""
    _set_person_away(hass, base_config)
    hass.states.async_set(base_config[CONF_ALARM], "off")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    coordinator._handle_alarm_state_change(_alarm_event(base_config, "on", "off"))
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 1
    assert coordinator.einsatz_count_responded == 0
    assert coordinator.einsatz_count_standby == 0


async def test_alarm_counted_as_responded_when_departed(
    hass: HomeAssistant, base_config
):
    """Departing (Einsatz minutes added on return) classifies as Abgerückt."""
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    _set_zone(hass, base_config)
    hass.states.async_set(base_config[CONF_ALARM], "on")

    # Leave zone during the alarm and return 2h later while still on.
    coordinator._on_zone_leave(datetime(2026, 7, 7, 17, 0), base_config[CONF_ALARM])
    await hass.async_block_till_done()
    coordinator._on_zone_enter(datetime(2026, 7, 7, 19, 0))
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 120
    assert coordinator._data[DATA_ALARM_RESPONDED] is True

    coordinator._handle_alarm_state_change(_alarm_event(base_config, "on", "off"))
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 1
    assert coordinator.einsatz_count_responded == 1
    assert coordinator.einsatz_count_standby == 0
    # Flags reset for the next alarm.
    assert coordinator._data[DATA_ALARM_RESPONDED] is False


async def test_alarm_counted_as_standby_via_flag(hass: HomeAssistant, base_config):
    """Present at the station during the alarm, no departure = Bereitschaft.

    The person is moved out before the off event so only the persisted
    at-station flag (set by the minute tick) can classify it.
    """
    _set_person_in_zone(hass, base_config)
    hass.states.async_set(base_config[CONF_ALARM], "on")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    coordinator._handle_minute_tick(None)  # in zone + alarm on -> at_station flag
    await hass.async_block_till_done()
    assert coordinator._data[DATA_ALARM_AT_STATION] is True

    # Move the person out so current-presence can't be the reason.
    hass.states.async_set(base_config[CONF_PERSON], "not_home")
    coordinator._handle_alarm_state_change(_alarm_event(base_config, "on", "off"))
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 1
    assert coordinator.einsatz_count_standby == 1
    assert coordinator.einsatz_count_responded == 0


async def test_short_alarm_uses_current_presence_fallback(
    hass: HomeAssistant, base_config
):
    """An alarm shorter than one tick still counts standby via current presence."""
    _set_person_in_zone(hass, base_config)
    hass.states.async_set(base_config[CONF_ALARM], "on")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    # No minute tick fired → at_station flag is still False.
    assert coordinator._data[DATA_ALARM_AT_STATION] is False

    coordinator._handle_alarm_state_change(_alarm_event(base_config, "on", "off"))
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 1
    assert coordinator.einsatz_count_standby == 1


async def test_unavailable_dropout_does_not_double_count(
    hass: HomeAssistant, base_config
):
    """on->unavailable->on->off counts exactly one alarm and keeps the flags."""
    _set_person_in_zone(hass, base_config)
    hass.states.async_set(base_config[CONF_ALARM], "on")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)

    coordinator._handle_minute_tick(None)  # at_station flag
    await hass.async_block_till_done()

    # Sensor briefly drops out mid-mission – must NOT count or reset flags.
    coordinator._handle_alarm_state_change(
        _alarm_event(base_config, "on", "unavailable")
    )
    await hass.async_block_till_done()
    assert coordinator.einsatz_count_total == 0
    assert coordinator._data[DATA_ALARM_AT_STATION] is True

    coordinator._handle_alarm_state_change(
        _alarm_event(base_config, "unavailable", "on")
    )
    await hass.async_block_till_done()
    assert coordinator._data[DATA_ALARM_AT_STATION] is True

    coordinator._handle_alarm_state_change(_alarm_event(base_config, "on", "off"))
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 1
    assert coordinator.einsatz_count_standby == 1


async def test_flags_reset_between_two_alarms(hass: HomeAssistant, base_config):
    """A new alarm (off->on) must not inherit the previous alarm's classification."""
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    _set_zone(hass, base_config)
    hass.states.async_set(base_config[CONF_ALARM], "on")

    # Alarm #1: departed -> Abgerückt.
    coordinator._on_zone_leave(datetime(2026, 7, 7, 17, 0), base_config[CONF_ALARM])
    await hass.async_block_till_done()
    coordinator._on_zone_enter(datetime(2026, 7, 7, 19, 0))
    await hass.async_block_till_done()
    coordinator._handle_alarm_state_change(_alarm_event(base_config, "on", "off"))
    await hass.async_block_till_done()
    assert coordinator.einsatz_count_responded == 1

    # New alarm starts (off -> on): flags reset.
    coordinator._handle_alarm_state_change(_alarm_event(base_config, "off", "on"))
    await hass.async_block_till_done()
    assert coordinator._data[DATA_ALARM_RESPONDED] is False
    assert coordinator._data[DATA_ALARM_AT_STATION] is False

    # Alarm #2: only standby this time.
    _set_person_in_zone(hass, base_config)
    hass.states.async_set(base_config[CONF_ALARM], "on")
    coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()
    hass.states.async_set(base_config[CONF_PERSON], "not_home")
    coordinator._handle_alarm_state_change(_alarm_event(base_config, "on", "off"))
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 2
    assert coordinator.einsatz_count_responded == 1  # unchanged
    assert coordinator.einsatz_count_standby == 1


# ----------------------------------------------------------------------
# Services
# ----------------------------------------------------------------------


async def test_add_count_clamps_at_zero(hass: HomeAssistant, base_config):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_count("gesamt", 3)
    await hass.async_block_till_done()
    assert coordinator.einsatz_count_total == 3

    coordinator.add_count("gesamt", -10)
    await hass.async_block_till_done()
    assert coordinator.einsatz_count_total == 0


async def test_reset_count_single_and_all(hass: HomeAssistant, base_config):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_count("gesamt", 5)
    coordinator.add_count("abgerueckt", 2)
    coordinator.add_count("bereitschaft", 3)
    await hass.async_block_till_done()

    coordinator.reset_count("abgerueckt")
    await hass.async_block_till_done()
    assert coordinator.einsatz_count_responded == 0
    assert coordinator.einsatz_count_total == 5

    coordinator.reset_count("all")
    await hass.async_block_till_done()
    assert coordinator.einsatz_count_total == 0
    assert coordinator.einsatz_count_standby == 0


# ----------------------------------------------------------------------
# Year rollover
# ----------------------------------------------------------------------


async def test_year_rollover_archives_and_resets_counts(
    hass: HomeAssistant, base_config
):
    _set_person_away(hass, base_config)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    coordinator.add_count("gesamt", 12)
    coordinator.add_count("abgerueckt", 5)
    coordinator.add_count("bereitschaft", 4)
    await hass.async_block_till_done()
    coordinator._data[DATA_CURRENT_YEAR] = 2026

    new_year = datetime(2027, 1, 1, 0, 1)
    with patch(
        "custom_components.feuerwehr_time_tracker.coordinator.dt_util.now",
        return_value=new_year,
    ):
        coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 0
    assert coordinator.einsatz_count_responded == 0
    assert coordinator.einsatz_count_standby == 0

    archived = coordinator.get_previous_years_data()["2026"]
    assert archived[DATA_COUNT_TOTAL] == 12
    assert archived[DATA_COUNT_RESPONDED] == 5
    assert archived[DATA_COUNT_STANDBY] == 4


# ----------------------------------------------------------------------
# Undo via actionable notification
# ----------------------------------------------------------------------


async def test_finalize_notify_attaches_reset_button(
    hass: HomeAssistant, notify_config
):
    """A counted alarm sends a notification with an 'Einsatz zurücksetzen' button."""
    calls = _register_notify(hass)
    _set_person_in_zone(hass, notify_config)
    hass.states.async_set(notify_config[CONF_ALARM], "on")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)

    coordinator._handle_minute_tick(None)  # at_station -> standby classification
    await hass.async_block_till_done()
    coordinator._handle_alarm_state_change(_alarm_event(notify_config, "on", "off"))
    await hass.async_block_till_done()

    undos = coordinator._data[DATA_PENDING_UNDOS]
    assert len(undos) == 1
    token, record = next(iter(undos.items()))
    assert record["type"] == UNDO_TYPE_COUNT
    assert set(record["increments"]) == {"gesamt", "bereitschaft"}

    action = calls[-1].data["data"]["actions"][0]
    assert action["title"] == "Einsatz zurücksetzen"
    assert calls[-1].data["data"]["tag"] == f"{NOTIFY_TAG_PREFIX}{token}"


async def test_try_undo_count_reverts_increments(hass: HomeAssistant, notify_config):
    """Undoing a count record reverts every counter incremented for that alarm."""
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)
    coordinator.add_count("gesamt", 3)
    coordinator.add_count("abgerueckt", 1)
    coordinator._data[DATA_PENDING_UNDOS] = {
        "TOK": {
            "type": UNDO_TYPE_COUNT,
            "increments": ["gesamt", "abgerueckt"],
            "created": 1.0,
        }
    }
    await hass.async_block_till_done()

    assert coordinator.try_undo("tok") is True  # case-insensitive
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 2
    assert coordinator.einsatz_count_responded == 0
    assert "TOK" not in coordinator._data[DATA_PENDING_UNDOS]

    confirmations = [
        c for c in calls if c.data.get("title") == "↩️ Einsatz zurückgesetzt"
    ]
    assert len(confirmations) == 1
    assert "actions" not in confirmations[0].data["data"]


async def test_count_notification_undo_end_to_end(hass: HomeAssistant, notify_config):
    """Full path: a counted standby alarm can be fully undone via its token."""
    _register_notify(hass)
    _set_person_in_zone(hass, notify_config)
    hass.states.async_set(notify_config[CONF_ALARM], "on")
    coordinator = FeuerwehrCoordinator(hass, "test_entry", notify_config)

    coordinator._handle_minute_tick(None)
    await hass.async_block_till_done()
    coordinator._handle_alarm_state_change(_alarm_event(notify_config, "on", "off"))
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 1
    assert coordinator.einsatz_count_standby == 1
    token = next(iter(coordinator._data[DATA_PENDING_UNDOS]))

    assert coordinator.try_undo(token) is True
    await hass.async_block_till_done()

    assert coordinator.einsatz_count_total == 0
    assert coordinator.einsatz_count_standby == 0
    assert coordinator._data[DATA_PENDING_UNDOS] == {}


async def test_counts_persist_across_reload(hass: HomeAssistant, base_config):
    """Mission counters survive a coordinator restart (merge-on-load, version 1)."""
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_test_entry")
    await store.async_save(
        {
            DATA_COUNT_TOTAL: 7,
            DATA_COUNT_RESPONDED: 3,
            DATA_COUNT_STANDBY: 2,
        }
    )

    coordinator = FeuerwehrCoordinator(hass, "test_entry", base_config)
    await coordinator.async_setup()
    try:
        assert coordinator.einsatz_count_total == 7
        assert coordinator.einsatz_count_responded == 3
        assert coordinator.einsatz_count_standby == 2
    finally:
        await coordinator.async_shutdown()
