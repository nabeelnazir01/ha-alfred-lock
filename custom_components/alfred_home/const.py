"""Constants for the Alfred Smart Lock Home Assistant integration."""

DOMAIN = "alfred_home"

CONF_ACCOUNT = "account"
CONF_PASSWORD = "password"

DEFAULT_NAME = "Alfred Smart Lock"
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Alfred API Endpoints
SDC_STARTUP_URL = "https://sdc-us.alfred-iot.com/api/v1/app-startup"
UAC_SERVER = "https://uac-us.alfred-iot.com/api"
HUB_SERVER = "https://hub-us-gw.alfred-iot.com/api"
LOCK_SERVER = "https://lock-us-gw.alfred-iot.com/api"

# Agent metadata
AGENT_TOKEN = "550e8400-e29b-41d4-a716-446655440000"
AGENT_NAME = "Home Assistant"
APP_VERSION = "1.9.25082001"
APP_VENDOR = "ALF"

# Device Types
DEVICE_TYPE_LOCK = 2
DEVICE_TYPE_BRIDGE = 8

# Binary frame command constants
CMD_DOOR_CONTROL = 0x02
PARAM_UNLOCK = 0
PARAM_LOCK = 1
