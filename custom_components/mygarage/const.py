"""Constants for the MyGarage integration."""

from __future__ import annotations

DOMAIN = "mygarage"

CONF_URL = "url"
CONF_WIDGET_API_KEY = "widget_api_key"
CONF_WEBHOOK_TOKEN = "webhook_token"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 3600

ATTR_VIN = "vin"

SERVICE_LOG_FUEL = "log_fuel"
SERVICE_LOG_ODOMETER = "log_odometer"
SERVICE_COMPLETE_REMINDER = "complete_reminder"
