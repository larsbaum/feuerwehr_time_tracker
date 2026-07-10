"""Tests for FeuerwehrCoordinator behavior."""
from datetime import datetime
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.feuerwehr_time_tracker.const import (
    CONF_ALARM,
    CONF_EINSATZ_MAX_HOURS,
    CONF_PERSON,
    CONF_PROBE_MODE,
    CONF_ZONE,
    PROBE_MODE_DAY_TIME,
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
    coordinator.add_minutes("geratehaus", 5)
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
    assert coordinator.geratehaus_minutes == 0


async def test_minute_tick_counts_as_geratehaus_outside_probe_window(
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

    assert coordinator.geratehaus_minutes == 1
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
    assert coordinator.geratehaus_minutes == 0
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
