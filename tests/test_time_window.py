"""Tests for the pure time/weekday helper functions in coordinator.py."""
from datetime import datetime, time as dtime

from custom_components.feuerwehr_time_tracker.coordinator import (
    _in_time_window,
    _is_probe_weekday,
    _parse_time,
)


def test_parse_time():
    assert _parse_time("07:30") == dtime(7, 30)
    assert _parse_time("23:59") == dtime(23, 59)
    assert _parse_time("00:00") == dtime(0, 0)


def test_in_time_window_normal_range():
    start, end = "17:00", "23:00"
    assert _in_time_window(datetime(2026, 7, 7, 17, 0), start, end) is True
    assert _in_time_window(datetime(2026, 7, 7, 20, 0), start, end) is True
    assert _in_time_window(datetime(2026, 7, 7, 23, 0), start, end) is True
    assert _in_time_window(datetime(2026, 7, 7, 16, 59), start, end) is False
    assert _in_time_window(datetime(2026, 7, 7, 23, 1), start, end) is False


def test_in_time_window_overnight_range():
    # Window spans midnight, e.g. 22:00 - 02:00
    start, end = "22:00", "02:00"
    assert _in_time_window(datetime(2026, 7, 7, 23, 30), start, end) is True
    assert _in_time_window(datetime(2026, 7, 8, 1, 30), start, end) is True
    assert _in_time_window(datetime(2026, 7, 7, 22, 0), start, end) is True
    assert _in_time_window(datetime(2026, 7, 8, 2, 0), start, end) is True
    assert _in_time_window(datetime(2026, 7, 7, 12, 0), start, end) is False


def test_is_probe_weekday():
    tuesday = datetime(2026, 7, 7)  # confirmed Tuesday
    wednesday = datetime(2026, 7, 8)

    assert _is_probe_weekday(tuesday, "tue") is True
    assert _is_probe_weekday(wednesday, "tue") is False
    assert _is_probe_weekday(wednesday, "wed") is True


def test_is_probe_weekday_unknown_key_defaults_to_tuesday():
    tuesday = datetime(2026, 7, 7)
    assert _is_probe_weekday(tuesday, "not_a_weekday") is True
