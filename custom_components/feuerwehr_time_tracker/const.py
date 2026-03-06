"""Constants for Feuerwehr Zeit-Tracker."""

DOMAIN = "feuerwehr_time_tracker"
PLATFORMS = ["sensor"]

# Config entry keys
CONF_PERSON = "person_entity"
CONF_ZONE = "zone_entity"
CONF_ALARM = "alarm_sensor"
CONF_PROBE_WEEKDAY = "probe_weekday"
CONF_PROBE_START = "probe_start"
CONF_PROBE_END = "probe_end"
CONF_PROBE_COUNT_START = "probe_count_start"
CONF_PROBE_COUNT_END = "probe_count_end"
CONF_EINSATZ_MAX_HOURS = "einsatz_max_hours"
CONF_NOTIFY_SERVICE = "notify_service"

# Storage
STORAGE_KEY = "feuerwehr_time_tracker"
STORAGE_VERSION = 1

# Data store keys
DATA_EINSATZ_MINUTES = "einsatz_minutes"
DATA_PROBE_MINUTES = "probe_minutes"
DATA_GERATEHAUS_MINUTES = "geratehaus_minutes"
DATA_EINSATZ_STARTED = "einsatz_started"   # timestamp float or None
DATA_PROBE_STARTED = "probe_started"       # timestamp float or None

# Sensor unique id suffixes
SENSOR_EINSATZ = "einsatz"
SENSOR_PROBE = "probe"
SENSOR_GERATEHAUS = "geratehaus"
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
