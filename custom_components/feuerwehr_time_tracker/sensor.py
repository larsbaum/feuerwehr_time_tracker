"""Sensor platform for Feuerwehr Zeit-Tracker."""
from __future__ import annotations

import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SENSOR_EINSATZ,
    SENSOR_PROBE,
    SENSOR_SONSTIGES,
    SENSOR_GESAMT,
    SENSOR_COUNT_TOTAL,
    SENSOR_COUNT_RESPONDED,
    SENSOR_COUNT_STANDBY,
    CONF_PERSON,
    DATA_EINSATZ_MINUTES,
    DATA_PROBE_MINUTES,
    DATA_SONSTIGES_MINUTES,
    DATA_COUNT_TOTAL,
    DATA_COUNT_RESPONDED,
    DATA_COUNT_STANDBY,
)
from .coordinator import FeuerwehrCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator: FeuerwehrCoordinator = hass.data[DOMAIN][entry.entry_id]

    person = entry.data.get(CONF_PERSON, "")
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Feuerwehr Zeit-Tracker",
        manufacturer="HACS Community",
        model="Zeit-Tracker",
        entry_type=DeviceEntryType.SERVICE,
    )

    sensors = [
        FeuerwehrSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            category=SENSOR_EINSATZ,
            name="Alarm Hours",
            icon="mdi:fire-truck",
            device_info=device_info,
        ),
        FeuerwehrSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            category=SENSOR_PROBE,
            name="Training Hours",
            icon="mdi:account-group",
            device_info=device_info,
        ),
        FeuerwehrSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            category=SENSOR_SONSTIGES,
            name="Other Hours",
            icon="mdi:home-group",
            device_info=device_info,
        ),
        FeuerwehrSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            category=SENSOR_GESAMT,
            name="Total Hours",
            icon="mdi:sigma",
            device_info=device_info,
        ),
        FeuerwehrCountSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            category=SENSOR_COUNT_TOTAL,
            name="Einsätze Gesamt",
            icon="mdi:counter",
            device_info=device_info,
        ),
        FeuerwehrCountSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            category=SENSOR_COUNT_RESPONDED,
            name="Einsätze Abgerückt",
            icon="mdi:fire-truck",
            device_info=device_info,
        ),
        FeuerwehrCountSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            category=SENSOR_COUNT_STANDBY,
            name="Einsätze Bereitschaft",
            icon="mdi:account-clock",
            device_info=device_info,
        ),
    ]

    async_add_entities(sensors)


class FeuerwehrSensor(SensorEntity):
    """A sensor that shows accumulated hours for one category."""

    _attr_native_unit_of_measurement = "h"
    _attr_state_class = "total_increasing"
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: FeuerwehrCoordinator,
        entry_id: str,
        category: str,
        name: str,
        icon: str,
        device_info: DeviceInfo,
    ) -> None:
        self._coordinator = coordinator
        self._category = category
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry_id}_{category}"
        self._attr_device_info = device_info

    def _current_minutes(self) -> int:
        """Live minutes for this sensor's category."""
        return {
            SENSOR_EINSATZ: self._coordinator.einsatz_minutes,
            SENSOR_PROBE: self._coordinator.probe_minutes,
            SENSOR_SONSTIGES: self._coordinator.sonstiges_minutes,
            SENSOR_GESAMT: self._coordinator.gesamt_minutes,
        }.get(self._category, 0)

    @property
    def native_value(self) -> float:
        """Return hours, rounded to 2 decimals."""
        return round(self._current_minutes() / 60, 2)

    @property
    def extra_state_attributes(self) -> dict:
        minutes = self._current_minutes()
        attrs = {
            "minutes": minutes,
            "hours": round(minutes / 60, 2),
        }

        previous_years = self._coordinator.get_previous_years_data()
        if self._category == SENSOR_GESAMT:
            # Full per-category breakdown on the total sensor. Sum only the three
            # minute keys explicitly – the archived dict also holds mission-count
            # keys, so a blanket sum(data.values()) would corrupt the total.
            attrs["previous_years"] = {}
            for year, data in previous_years.items():
                total_minutes = (
                    data.get(DATA_EINSATZ_MINUTES, 0)
                    + data.get(DATA_PROBE_MINUTES, 0)
                    + data.get(DATA_SONSTIGES_MINUTES, 0)
                )
                attrs["previous_years"][year] = {
                    "einsatz_minutes": data.get(DATA_EINSATZ_MINUTES, 0),
                    "einsatz_hours": round(data.get(DATA_EINSATZ_MINUTES, 0) / 60, 2),
                    "probe_minutes": data.get(DATA_PROBE_MINUTES, 0),
                    "probe_hours": round(data.get(DATA_PROBE_MINUTES, 0) / 60, 2),
                    "sonstiges_minutes": data.get(DATA_SONSTIGES_MINUTES, 0),
                    "sonstiges_hours": round(data.get(DATA_SONSTIGES_MINUTES, 0) / 60, 2),
                    "gesamt_minutes": total_minutes,
                    "gesamt_hours": round(total_minutes / 60, 2),
                }
        else:
            data_key = {
                SENSOR_EINSATZ: DATA_EINSATZ_MINUTES,
                SENSOR_PROBE: DATA_PROBE_MINUTES,
                SENSOR_SONSTIGES: DATA_SONSTIGES_MINUTES,
            }.get(self._category)
            if data_key:
                attrs["previous_years"] = {
                    year: {
                        "minutes": data.get(data_key, 0),
                        "hours": round(data.get(data_key, 0) / 60, 2),
                    }
                    for year, data in previous_years.items()
                }
        return attrs

    async def async_added_to_hass(self) -> None:
        """Register with coordinator for updates."""
        self._coordinator.register_sensor(self._update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from coordinator."""
        self._coordinator.unregister_sensor(self._update_callback)

    @callback
    def _update_callback(self) -> None:
        """Coordinator notified us of a data change."""
        self.async_write_ha_state()


class FeuerwehrCountSensor(SensorEntity):
    """A diagnostic sensor that shows a mission counter (Einsatzzahl).

    Grouped under the device's "Diagnostic" section (entity_category), keeping
    the mission counters visually separate from the hour sensors. Uses
    state_class total_increasing so it survives the yearly reset natively.
    """

    _attr_state_class = "total_increasing"
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FeuerwehrCoordinator,
        entry_id: str,
        category: str,
        name: str,
        icon: str,
        device_info: DeviceInfo,
    ) -> None:
        self._coordinator = coordinator
        self._category = category
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry_id}_{category}"
        self._attr_device_info = device_info

    def _current_count(self) -> int:
        """Live count for this sensor's category."""
        return {
            SENSOR_COUNT_TOTAL: self._coordinator.einsatz_count_total,
            SENSOR_COUNT_RESPONDED: self._coordinator.einsatz_count_responded,
            SENSOR_COUNT_STANDBY: self._coordinator.einsatz_count_standby,
        }.get(self._category, 0)

    @property
    def native_value(self) -> int:
        return self._current_count()

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {"count": self._current_count()}
        previous_years = self._coordinator.get_previous_years_data()

        if self._category == SENSOR_COUNT_TOTAL:
            # Full per-category breakdown on the "Gesamt" counter.
            attrs["previous_years"] = {
                year: {
                    "gesamt": data.get(DATA_COUNT_TOTAL, 0),
                    "abgerueckt": data.get(DATA_COUNT_RESPONDED, 0),
                    "bereitschaft": data.get(DATA_COUNT_STANDBY, 0),
                }
                for year, data in previous_years.items()
            }
        else:
            data_key = {
                SENSOR_COUNT_RESPONDED: DATA_COUNT_RESPONDED,
                SENSOR_COUNT_STANDBY: DATA_COUNT_STANDBY,
            }.get(self._category)
            if data_key:
                attrs["previous_years"] = {
                    year: {"count": data.get(data_key, 0)}
                    for year, data in previous_years.items()
                }
        return attrs

    async def async_added_to_hass(self) -> None:
        self._coordinator.register_sensor(self._update_callback)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(self._update_callback)

    @callback
    def _update_callback(self) -> None:
        self.async_write_ha_state()
