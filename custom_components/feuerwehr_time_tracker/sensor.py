"""Sensor platform for Feuerwehr Zeit-Tracker."""
from __future__ import annotations

import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
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
    CONF_PERSON,
    DATA_EINSATZ_MINUTES,
    DATA_PROBE_MINUTES,
    DATA_SONSTIGES_MINUTES,
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
            # Full per-category breakdown on the total sensor
            attrs["previous_years"] = {
                year: {
                    "einsatz_minutes": data.get(DATA_EINSATZ_MINUTES, 0),
                    "einsatz_hours": round(data.get(DATA_EINSATZ_MINUTES, 0) / 60, 2),
                    "probe_minutes": data.get(DATA_PROBE_MINUTES, 0),
                    "probe_hours": round(data.get(DATA_PROBE_MINUTES, 0) / 60, 2),
                    "sonstiges_minutes": data.get(DATA_SONSTIGES_MINUTES, 0),
                    "sonstiges_hours": round(data.get(DATA_SONSTIGES_MINUTES, 0) / 60, 2),
                    "gesamt_minutes": sum(data.values()),
                    "gesamt_hours": round(sum(data.values()) / 60, 2),
                }
                for year, data in previous_years.items()
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
