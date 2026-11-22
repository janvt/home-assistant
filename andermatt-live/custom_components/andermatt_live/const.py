"""Constants of Andermatt Live."""

import datetime

DOMAIN = "andermatt_live"

CONF_SECTORS = "sectors"

# Identifies the integration to the site, so that its operators can see where
# the requests come from.
USER_AGENT = (
    "Andermatt Live Home Assistant integration"
    " (+https://github.com/janvt/home-assistant/tree/main/andermatt-live)"
)
ATTRIBUTION = "Data: Andermatt-Sedrun Sport AG, A+S+D Live Dashboard"
MANUFACTURER = "Andermatt+Sedrun+Disentis"

# Three requests per sector each time.  Lifts open and close a few times a day,
# so this is often enough to follow them without leaning on the site.
UPDATE_INTERVAL = datetime.timedelta(minutes=10)
