"""The Alfred Smart Lock Home Assistant Integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .alfred_api import AlfredApiClient
from .const import CONF_ACCOUNT, CONF_PASSWORD, DOMAIN
from .coordinator import AlfredDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LOCK,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alfred Smart Lock from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    account = entry.data[CONF_ACCOUNT]
    password = entry.data.get(CONF_PASSWORD)
    tokens = entry.data.get("tokens")

    client = AlfredApiClient(
        account=account,
        password=password,
        session=session,
        tokens=tokens,
    )

    # Initial device list fetch or refresh
    try:
        devices = await client.get_devices()
    except Exception as err:
        _LOGGER.warning("Could not refresh devices from cloud: %s", err)
        devices = entry.data.get("devices", [])

    coordinator = AlfredDataUpdateCoordinator(hass, client, devices)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "devices": devices,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client: AlfredApiClient = data["client"]
        await client.close()

    return unload_ok
