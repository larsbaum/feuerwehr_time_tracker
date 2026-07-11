"""Tests for the undo-via-notification event wiring (__init__)."""
from homeassistant.core import HomeAssistant, callback

from custom_components.feuerwehr_time_tracker import (
    UNDO_LISTENERS_KEY,
    _register_undo_listener,
)
from custom_components.feuerwehr_time_tracker.const import (
    CONF_NOTIFY_SERVICE,
    DATA_PENDING_UNDOS,
    DOMAIN,
    EVENT_IOS_NOTIFICATION_ACTION,
    EVENT_MOBILE_APP_NOTIFICATION_ACTION,
    UNDO_ACTION_PREFIX,
)
from custom_components.feuerwehr_time_tracker.coordinator import FeuerwehrCoordinator


def _make_coordinator(hass: HomeAssistant) -> FeuerwehrCoordinator:
    """Register a fake notify service and a coordinator with one pending undo."""

    @callback
    def _record(call) -> None:  # noqa: ANN001
        pass

    hass.services.async_register("notify", "mobile_app_test", _record)

    coordinator = FeuerwehrCoordinator(
        hass, "entry1", {CONF_NOTIFY_SERVICE: "notify.mobile_app_test"}
    )
    coordinator.add_minutes("einsatz", 100)
    coordinator._data[DATA_PENDING_UNDOS] = {
        "ABCD1234": {"category": "einsatz", "minutes": 60, "created": 1.0}
    }
    hass.data.setdefault(DOMAIN, {})["entry1"] = coordinator
    return coordinator


async def test_mobile_app_action_event_triggers_undo(hass: HomeAssistant):
    """A tapped action (as iOS delivers it, uppercase) subtracts the minutes."""
    coordinator = _make_coordinator(hass)
    _register_undo_listener(hass)

    hass.bus.async_fire(
        EVENT_MOBILE_APP_NOTIFICATION_ACTION,
        {"action": f"{UNDO_ACTION_PREFIX}ABCD1234"},
    )
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 40  # 100 - 60
    assert coordinator._data[DATA_PENDING_UNDOS] == {}


async def test_ios_action_event_with_actionname_triggers_undo(hass: HomeAssistant):
    """The older iOS event carries the identifier under 'actionName'."""
    coordinator = _make_coordinator(hass)
    _register_undo_listener(hass)

    hass.bus.async_fire(
        EVENT_IOS_NOTIFICATION_ACTION,
        {"actionName": f"{UNDO_ACTION_PREFIX}ABCD1234"},
    )
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 40


async def test_lowercase_action_still_matches(hass: HomeAssistant):
    """Even a lower-cased identifier is normalised and matches the record."""
    coordinator = _make_coordinator(hass)
    _register_undo_listener(hass)

    hass.bus.async_fire(
        EVENT_MOBILE_APP_NOTIFICATION_ACTION,
        {"action": f"{UNDO_ACTION_PREFIX}ABCD1234".lower()},
    )
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 40


async def test_unrelated_action_is_ignored(hass: HomeAssistant):
    """Actions from other integrations must not touch our counters."""
    coordinator = _make_coordinator(hass)
    _register_undo_listener(hass)

    hass.bus.async_fire(
        EVENT_MOBILE_APP_NOTIFICATION_ACTION, {"action": "SOME_OTHER_ACTION"}
    )
    await hass.async_block_till_done()

    assert coordinator.einsatz_minutes == 100
    assert "ABCD1234" in coordinator._data[DATA_PENDING_UNDOS]


async def test_register_undo_listener_stores_unsubs(hass: HomeAssistant):
    """The listener registration stashes its unsubscribe callbacks."""
    _register_undo_listener(hass)
    assert len(hass.data[UNDO_LISTENERS_KEY]) == 2
