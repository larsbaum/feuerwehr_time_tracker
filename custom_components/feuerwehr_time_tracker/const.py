"""Constants for Feuerwehr Zeit-Tracker."""
import json
import os

DOMAIN = "feuerwehr_time_tracker"
PLATFORMS = ["sensor"]

# Single source of truth for the integration/card version is manifest.json.
# Bump the version there only – CARD_VERSION (used for cache-busting the
# frontend card URL) is derived from it automatically.
with open(os.path.join(os.path.dirname(__file__), "manifest.json"), encoding="utf-8") as _f:
    CARD_VERSION = json.load(_f)["version"]

# Config entry keys
CONF_PERSON = "person_entity"
CONF_ZONE = "zone_entity"
CONF_ALARM = "alarm_sensor"
CONF_PROBE_WEEKDAY = "probe_weekday"
CONF_PROBE_START = "probe_start"
CONF_PROBE_END = "probe_end"
CONF_PROBE_COUNT_START = "probe_count_start"
CONF_PROBE_COUNT_END = "probe_count_end"
CONF_PROBE_MODE = "probe_mode"
CONF_PROBE_CALENDAR = "probe_calendar_entity"
CONF_PROBE_KEYWORDS = "probe_keywords"
CONF_EINSATZ_MAX_HOURS = "einsatz_max_hours"
CONF_PROBE_MAX_HOURS = "probe_max_hours"
CONF_TRACK_OTHER_ABSENCE = "track_other_absence"
CONF_SONSTIGES_MAX_HOURS = "sonstiges_max_hours"
CONF_NOTIFY_SERVICE = "notify_service"

# Probe mode choices
PROBE_MODE_DAY_TIME = "day_time"
PROBE_MODE_CALENDAR = "calendar"
PROBE_MODE_BOTH = "both"

# Storage
STORAGE_KEY = "feuerwehr_time_tracker"
STORAGE_VERSION = 1

# Data store keys
DATA_EINSATZ_MINUTES = "einsatz_minutes"
DATA_PROBE_MINUTES = "probe_minutes"
DATA_SONSTIGES_MINUTES = "sonstiges_minutes"
DATA_EINSATZ_STARTED = "einsatz_started"   # timestamp float or None
DATA_PROBE_STARTED = "probe_started"       # timestamp float or None
DATA_SONSTIGES_STARTED = "sonstiges_started"  # timestamp float or None
DATA_CURRENT_YEAR = "current_year"         # int or None (year the counters belong to)
DATA_PREVIOUS_YEARS = "previous_years"     # dict[str, dict[str, int]] archived totals

# Legacy keys (pre-rename "geratehaus" -> "sonstiges"), only used for migration
LEGACY_DATA_GERATEHAUS_MINUTES = "geratehaus_minutes"
LEGACY_SENSOR_GERATEHAUS = "geratehaus"

# Sensor unique id suffixes
SENSOR_EINSATZ = "einsatz"
SENSOR_PROBE = "probe"
SENSOR_SONSTIGES = "sonstiges"
SENSOR_GESAMT = "gesamt"

# Services
SERVICE_RESET = "reset"
SERVICE_ADD_MINUTES = "add_minutes"

# Weekday mapping: HA weekday int (0=Mon) → isoweekday (Mon=1)
WEEKDAY_OPTIONS = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

WEEKDAY_LABELS = {
    "mon": "Montag",
    "tue": "Dienstag",
    "wed": "Mittwoch",
    "thu": "Donnerstag",
    "fri": "Freitag",
    "sat": "Samstag",
    "sun": "Sonntag",
}
