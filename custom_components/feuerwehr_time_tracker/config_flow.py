"""Config flow for Feuerwehr Zeit-Tracker."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
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
    WEEKDAY_OPTIONS,
    WEEKDAY_LABELS,
)


def _get_person_entities(hass: HomeAssistant) -> list[str]:
    return [s.entity_id for s in hass.states.async_all("person")]


def _get_zone_entities(hass: HomeAssistant) -> list[str]:
    return [s.entity_id for s in hass.states.async_all("zone") if s.entity_id != "zone.home"]


def _get_binary_sensor_entities(hass: HomeAssistant) -> list[str]:
    return [s.entity_id for s in hass.states.async_all("binary_sensor")]


class FeuerwehrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle setup config flow."""

    VERSION = 1

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Person, Zone, Alarm."""
        errors = {}
        persons = _get_person_entities(self.hass)
        zones = _get_zone_entities(self.hass)
        sensors = _get_binary_sensor_entities(self.hass)

        if not persons:
            errors["base"] = "no_person"
        if not zones:
            errors["base"] = "no_zone"

        if user_input is not None and not errors:
            self._data.update(user_input)
            return await self.async_step_probe()

        schema = vol.Schema({
            vol.Required(CONF_PERSON, default=persons[0] if persons else ""): vol.In(persons) if persons else str,
            vol.Required(CONF_ZONE, default=zones[0] if zones else ""): vol.In(zones) if zones else str,
            vol.Required(CONF_ALARM, default=""): vol.In(sensors) if sensors else str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_probe(self, user_input=None):
        """Step 2: Probe / Übungs-Einstellungen."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_einsatz()

        schema = vol.Schema({
            vol.Required(CONF_PROBE_WEEKDAY, default="tue"): vol.In(list(WEEKDAY_OPTIONS.keys())),
            vol.Required(CONF_PROBE_START, default="17:00"): str,
            vol.Required(CONF_PROBE_END, default="23:59"): str,
            vol.Required(CONF_PROBE_COUNT_START, default="19:00"): str,
            vol.Required(CONF_PROBE_COUNT_END, default="23:00"): str,
        })

        return self.async_show_form(
            step_id="probe",
            data_schema=schema,
        )

    async def async_step_einsatz(self, user_input=None):
        """Step 3: Einsatz & Benachrichtigung."""
        if user_input is not None:
            self._data.update(user_input)
            title = f"Feuerwehr Zeit-Tracker ({self._data[CONF_PERSON]})"
            return self.async_create_entry(title=title, data=self._data)

        schema = vol.Schema({
            vol.Required(CONF_EINSATZ_MAX_HOURS, default=10): vol.All(int, vol.Range(min=1, max=24)),
            vol.Optional(CONF_NOTIFY_SERVICE, default=""): str,
        })

        return self.async_show_form(
            step_id="einsatz",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FeuerwehrOptionsFlow(config_entry)


class FeuerwehrOptionsFlow(config_entries.OptionsFlow):
    """Options flow for reconfiguring."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        """Show options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._entry.data, **self._entry.options}
        persons = _get_person_entities(self.hass)
        zones = _get_zone_entities(self.hass)
        sensors = _get_binary_sensor_entities(self.hass)

        schema = vol.Schema({
            vol.Required(CONF_PERSON, default=current.get(CONF_PERSON, "")): vol.In(persons) if persons else str,
            vol.Required(CONF_ZONE, default=current.get(CONF_ZONE, "")): vol.In(zones) if zones else str,
            vol.Required(CONF_ALARM, default=current.get(CONF_ALARM, "")): vol.In(sensors) if sensors else str,
            vol.Required(CONF_PROBE_WEEKDAY, default=current.get(CONF_PROBE_WEEKDAY, "tue")): vol.In(list(WEEKDAY_OPTIONS.keys())),
            vol.Required(CONF_PROBE_START, default=current.get(CONF_PROBE_START, "17:00")): str,
            vol.Required(CONF_PROBE_END, default=current.get(CONF_PROBE_END, "23:59")): str,
            vol.Required(CONF_PROBE_COUNT_START, default=current.get(CONF_PROBE_COUNT_START, "19:00")): str,
            vol.Required(CONF_PROBE_COUNT_END, default=current.get(CONF_PROBE_COUNT_END, "23:00")): str,
            vol.Required(CONF_EINSATZ_MAX_HOURS, default=current.get(CONF_EINSATZ_MAX_HOURS, 10)): vol.All(int, vol.Range(min=1, max=24)),
            vol.Optional(CONF_NOTIFY_SERVICE, default=current.get(CONF_NOTIFY_SERVICE, "")): str,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
