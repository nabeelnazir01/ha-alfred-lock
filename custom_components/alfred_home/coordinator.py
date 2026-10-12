"""DataUpdateCoordinator for Alfred Smart Lock integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .alfred_api import AlfredApiClient, AlfredApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AlfredDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Alfred hardware status from the cloud."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AlfredApiClient,
        devices: list[dict[str, Any]],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.devices = devices

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch real-time data for all locks via their linked bridges."""
        status_data: dict[str, Any] = {}

        if not self.devices:
            try:
                self.devices = await self.client.get_devices()
            except Exception as err:
                _LOGGER.warning("Could not refresh devices in coordinator: %s", err)

        for device in self.devices:
            if not device.get("isLock"):
                continue

            lock_id = device["deviceId"]
            master_id = device.get("masterId")

            if not master_id:
                # Find fallback bridge
                bridge = next((d for d in self.devices if d.get("isBridge")), None)
                master_id = bridge["deviceId"] if bridge else "G3B9BMOWNI2D0XT9"

            try:
                device_status = await self.client.get_device_status(master_id, lock_id)
                status_data[lock_id] = device_status
            except Exception as err:
                _LOGGER.warning("Error fetching status for %s: %s", lock_id, err)
                # Keep previous state if available, or initialize safe default state
                if self.data and lock_id in self.data:
                    status_data[lock_id] = self.data[lock_id]
                else:
                    status_data[lock_id] = {
                        "bridge_online": True,
                        "lock_online": True,
                        "is_locked": True,
                        "door_sensor_open": False,
                        "ble_signal": None,
                        "ble_signal_ts": None,
                        "malfunction": False,
                    }

        return status_data
