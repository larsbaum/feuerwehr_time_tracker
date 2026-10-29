"""Tests for the configurable notification modes (multi-select).

Three independent switches: OUTSIDE (per außerhalb event, with undo), STATION
(per Gerätehaus presence, with undo) and DAILY (23:59 summary, info only).
"""
from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from custom_components.feuerwehr_time_tracker.const import (
    CONF_ALARM,
    CONF_EINSATZ_MAX_HOURS,
    CONF_NOTIFY_EVENTS,
    CONF_NOTIFY_SERVICE,
    CONF_PERSON,
    CONF_PROBE_MODE,
    CONF_ZONE,
    DAILY_SUMMARY_MIN_MINUTES,
    DATA_DAILY_LAST_SENT,
    DATA_PENDING_UNDOS,
    DATA_STATION_SESSION,
    DATA_TODAY_DATE,
    DATA_TODAY_MINUTES,
    NOTIFY_EVENT_DAILY,
    NOTIFY_EVENT_OUTSIDE,
    NOTIFY_EVENT_STATION,
    NOTIFY_TAG_PREFIX,
    PROBE_MODE_DAY_TIME,
    UNDO_ACTION_PREFIX,
)
from custom_components.feuerwehr_time_tracker.coordinator import FeuerwehrCoordinator


def _config(events) -> dict:
    return {
        CONF_PERSON: "person.max",
        CONF_ZONE: "zone.geratehaus",
        CONF_ALARM: "binary_sensor.alarm",
        CONF_EINSATZ_MAX_HOURS: 10,
        CONF_PROBE_MODE: PROBE_MODE_DAY_TIME,
        CONF_NOTIFY_SERVICE: "notify.mobile_app_test",
        CONF_NOTIFY_EVENTS: events,
    }


def _register_notify(hass: HomeAssistant) -> list:
    calls: list = []

    @callback
    def _record(call) -> None:
        calls.append(call)

    hass.services.async_register("notify", "mobile_app_test", _record)
    return calls


def _today() -> str:
    return dt_util.now().date().isoformat()


def _yesterday() -> str:
    return (dt_util.now().date() - timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# _notify_enabled / backwards compatibility
# ---------------------------------------------------------------------------


async def test_default_is_outside_only(hass: HomeAssistant):
    """A config without the option behaves exactly like before: outside only."""
    cfg = _config([])
    del cfg[CONF_NOTIFY_EVENTS]
    coordinator = FeuerwehrCoordinator(hass, "test_entry", cfg)

    assert coordinator._notify_enabled(NOTIFY_EVENT_OUTSIDE) is True
    assert coordinator._notify_enabled(NOTIFY_EVENT_STATION) is False
    assert coordinator._notify_enabled(NOTIFY_EVENT_DAILY) is False


async def test_empty_selection_means_all_off(hass: HomeAssistant):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([]))
    assert coordinator._notify_enabled(NOTIFY_EVENT_OUTSIDE) is False
    assert coordinator._notify_enabled(NOTIFY_EVENT_STATION) is False
    assert coordinator._notify_enabled(NOTIFY_EVENT_DAILY) is False


# ---------------------------------------------------------------------------
# Gerätehaus-Aufenthalt (STATION)
# ---------------------------------------------------------------------------


async def test_station_flush_notifies_with_undo(hass: HomeAssistant):
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_STATION]))
    coordinator.add_minutes("probe", 42)
    coordinator._data[DATA_STATION_SESSION] = {"probe": 42}

    coordinator._flush_station_session()
    await hass.async_block_till_done()

    # One pending undo record for exactly this presence.
    undos = coordinator._data[DATA_PENDING_UNDOS]
    assert len(undos) == 1
    token, record = next(iter(undos.items()))
    assert record["category"] == "probe"
    assert record["minutes"] == 42

    # Notification carries the long-press undo action, and session was reset.
    payload = calls[-1].data
    assert payload["data"]["actions"][0]["action"] == f"{UNDO_ACTION_PREFIX}{token}"
    assert coordinator._data[DATA_STATION_SESSION] == {}


async def test_station_flush_disabled_resets_without_notify(hass: HomeAssistant):
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_OUTSIDE]))
    coordinator._data[DATA_STATION_SESSION] = {"sonstiges": 10}

    coordinator._flush_station_session()
    await hass.async_block_till_done()

    assert calls == []
    assert coordinator._data[DATA_STATION_SESSION] == {}
    assert coordinator._data[DATA_PENDING_UNDOS] == {}


async def test_track_station_minute_accumulates_session_and_today(hass: HomeAssistant):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_STATION]))

    coordinator._track_station_minute("einsatz")
    coordinator._track_station_minute("einsatz")

    assert coordinator._data[DATA_STATION_SESSION]["einsatz"] == 2
    assert coordinator._data[DATA_TODAY_MINUTES]["einsatz"] == 2
    assert coordinator._data[DATA_TODAY_DATE] == _today()


# ---------------------------------------------------------------------------
# Tages-Akkumulator (_add_today)
# ---------------------------------------------------------------------------


async def test_add_today_rolls_over_on_new_day(hass: HomeAssistant):
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_DAILY]))
    coordinator._data[DATA_TODAY_DATE] = _yesterday()
    coordinator._data[DATA_TODAY_MINUTES] = {"probe": 99}

    coordinator._add_today("einsatz", 5)

    assert coordinator._data[DATA_TODAY_DATE] == _today()
    assert coordinator._data[DATA_TODAY_MINUTES] == {"einsatz": 5}


# ---------------------------------------------------------------------------
# Tagesende-Zusammenfassung (DAILY)
# ---------------------------------------------------------------------------


async def test_daily_summary_sends_breakdown_above_threshold(hass: HomeAssistant):
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_DAILY]))
    coordinator._data[DATA_TODAY_DATE] = _today()
    coordinator._data[DATA_TODAY_MINUTES] = {"einsatz": 20, "probe": 10}

    coordinator._send_daily_summary(dt_util.now())
    await hass.async_block_till_done()

    assert len(calls) == 1
    payload = calls[-1].data
    assert payload["title"] == "📊 Feuerwehr Tagesbericht"
    assert "Einsatz" in payload["message"] and "Probe" in payload["message"]
    assert "Gesamt" in payload["message"]
    # No action buttons on the summary.
    assert "actions" not in payload.get("data", {})
    assert coordinator._data[DATA_DAILY_LAST_SENT] == _today()


async def test_daily_summary_below_threshold_not_sent(hass: HomeAssistant):
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_DAILY]))
    coordinator._data[DATA_TODAY_DATE] = _today()
    coordinator._data[DATA_TODAY_MINUTES] = {"probe": DAILY_SUMMARY_MIN_MINUTES - 1}

    coordinator._send_daily_summary(dt_util.now())
    await hass.async_block_till_done()

    assert calls == []
    assert coordinator._data[DATA_DAILY_LAST_SENT] is None


async def test_daily_summary_not_sent_when_disabled(hass: HomeAssistant):
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_OUTSIDE]))
    coordinator._data[DATA_TODAY_DATE] = _today()
    coordinator._data[DATA_TODAY_MINUTES] = {"einsatz": 60}

    coordinator._send_daily_summary(dt_util.now())
    await hass.async_block_till_done()

    assert calls == []


async def test_daily_summary_deduplicated_same_day(hass: HomeAssistant):
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_DAILY]))
    coordinator._data[DATA_TODAY_DATE] = _today()
    coordinator._data[DATA_TODAY_MINUTES] = {"einsatz": 30}

    coordinator._send_daily_summary(dt_util.now())
    coordinator._send_daily_summary(dt_util.now())
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_daily_catchup_sends_for_missed_past_day(hass: HomeAssistant):
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_DAILY]))
    coordinator._data[DATA_TODAY_DATE] = _yesterday()
    coordinator._data[DATA_TODAY_MINUTES] = {"sonstiges": 30}

    coordinator._maybe_send_daily_catchup()
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert coordinator._data[DATA_DAILY_LAST_SENT] == _yesterday()


async def test_daily_catchup_skips_current_day(hass: HomeAssistant):
    calls = _register_notify(hass)
    coordinator = FeuerwehrCoordinator(hass, "test_entry", _config([NOTIFY_EVENT_DAILY]))
    coordinator._data[DATA_TODAY_DATE] = _today()
    coordinator._data[DATA_TODAY_MINUTES] = {"einsatz": 30}

    coordinator._maybe_send_daily_catchup()
    await hass.async_block_till_done()

    # Today's summary still fires at 23:59 – catch-up must not pre-empt it.
    assert calls == []
