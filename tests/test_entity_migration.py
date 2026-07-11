"""Tests for the one-time entity registry migration (geratehaus -> sonstiges)."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.feuerwehr_time_tracker import _async_migrate_geratehaus_entity
from custom_components.feuerwehr_time_tracker.const import DOMAIN


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    return entry


async def test_migrates_unique_id_and_entity_id(hass: HomeAssistant):
    entry = _make_entry(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_geratehaus",
        suggested_object_id="station_hours",
        config_entry=entry,
    )
    assert registry.async_get("sensor.station_hours") is not None

    _async_migrate_geratehaus_entity(hass, entry)

    migrated = registry.async_get("sensor.other_hours")
    assert migrated is not None
    assert migrated.unique_id == f"{entry.entry_id}_sonstiges"
    # Old identity is gone
    assert registry.async_get("sensor.station_hours") is None
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_geratehaus")
        is None
    )


async def test_migration_is_noop_without_legacy_entity(hass: HomeAssistant):
    entry = _make_entry(hass)
    registry = er.async_get(hass)
    # Fresh install: only the new unique_id exists already
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_sonstiges",
        suggested_object_id="other_hours",
        config_entry=entry,
    )

    _async_migrate_geratehaus_entity(hass, entry)

    migrated = registry.async_get("sensor.other_hours")
    assert migrated is not None
    assert migrated.unique_id == f"{entry.entry_id}_sonstiges"


async def test_migration_removes_orphan_when_unique_id_taken(hass: HomeAssistant):
    """Both identities exist: the legacy orphan is removed, no crash."""
    entry = _make_entry(hass)
    registry = er.async_get(hass)

    # The new "_sonstiges" identity already exists (e.g. fresh sensor created).
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_sonstiges",
        suggested_object_id="feuerwehr_zeit_tracker_other_hours",
        config_entry=entry,
    )
    # ...and a leftover legacy "_geratehaus" entity still lingers.
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_geratehaus",
        suggested_object_id="station_hours",
        config_entry=entry,
    )

    # Must not raise (previously crashed with a unique_id ValueError).
    _async_migrate_geratehaus_entity(hass, entry)

    # The orphan is gone, the sonstiges identity is untouched.
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_geratehaus")
        is None
    )
    sonstiges_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_sonstiges"
    )
    assert sonstiges_id is not None
    assert registry.async_get(sonstiges_id) is not None


async def test_migration_keeps_entity_id_when_target_taken(hass: HomeAssistant):
    """Second config entry: sensor.other_hours already exists -> keep old id."""
    registry = er.async_get(hass)

    entry_one = _make_entry(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry_one.entry_id}_sonstiges",
        suggested_object_id="other_hours",
        config_entry=entry_one,
    )

    entry_two = _make_entry(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry_two.entry_id}_geratehaus",
        suggested_object_id="station_hours_2",
        config_entry=entry_two,
    )

    _async_migrate_geratehaus_entity(hass, entry_two)

    # unique_id migrated, entity_id kept because target was taken
    kept = registry.async_get("sensor.station_hours_2")
    assert kept is not None
    assert kept.unique_id == f"{entry_two.entry_id}_sonstiges"
