"""Names shared by the integration and `dashboards/mobile-alerts/`.

No Home Assistant imports: `build.py` and the repo's plain test suite read this
file directly, so the dashboard and the integration can't drift apart.
"""
DOMAIN = "alert_pills"

# Entity ids. The pills keep the ids the old template helpers had, so history,
# the dashboard and pills that read other pills carry on unchanged.
PILL_ENTITY = "binary_sensor.pill_{key}"
COUNT_ENTITY = "sensor.weather_alerts_active"
ROW_ENTITY = "sensor.alert_pills_row"

# Options, set in Settings → Devices & services → Alert pills → Configure.
CONF_DISABLED = "disabled"
CONF_DISABLED_GROUPS = "disabled_groups"
CONF_CARD_ONLY = "card_only"
CONF_PLACES = "places"
DEFAULT_PLACES = 6
# The dashboard has this many chips in the row; `places` hides the rest.
MAX_PLACES = 10

# What `alert_pills.load` takes per pill. `state`, `color` and `content` are
# templates (a plain colour is a template that renders to itself).
PILL_FIELDS = {"key", "name", "group", "icon", "color", "state", "content", "critical"}

SERVICE_LOAD = "load"
SERVICE_DISMISS = "dismiss"
SERVICE_RESTORE = "restore"
SERVICE_TOGGLE_DISMISS = "toggle_dismiss"
