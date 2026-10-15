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
                # Fetch detailed attributes including battery, user profiles, model, and unlock logs
                try:
                    detail = await self.client.get_lock_detail(lock_id)
                    device_status["battery"] = detail.get("battery")
                    device_status["battery_time"] = detail.get("battery_time")

                    model_name = detail.get("model")
                    if model_name:
                        device["model"] = model_name
                        device_status["model"] = model_name
                    fw_version = detail.get("fw_version")
                    if fw_version:
                        device["fw_version"] = fw_version
                        device_status["fw_version"] = fw_version

                    has_doorsensor = detail.get("has_doorsensor", False)
                    device["has_doorsensor"] = has_doorsensor
                    device_status["has_doorsensor"] = has_doorsensor

                    mongo_id = detail.get("mongodb_id")
                    if mongo_id:
                        device_status["mongo_id"] = mongo_id
                        # 1. Fetch user PIN profiles (KeyPersons)
                        try:
                            keypersons = await self.client.get_lock_keypersons(mongo_id)
                            device_status["keypersons"] = keypersons

                            pin_users = {}
                            for kp in keypersons:
                                kp_name = kp.get("name")
                                kp_idx = kp.get("index")
                                kp_type = kp.get("type", 0)
                                if kp_name and kp_idx is not None:
                                    pin_users[str(kp_idx)] = kp_name
                            device_status["pin_users"] = pin_users
                        except Exception as kp_err:
                            _LOGGER.debug("Could not fetch keypersons for %s: %s", lock_id, kp_err)

                        # 2. Fetch latest unlock activity log
                        try:
                            logs = await self.client.get_lock_activity_logs(mongo_id, limit=10)
                            device_status["logs"] = logs

                            # Find most recent unlock event (lockevent == 4)
                            last_unlock = next(
                                (item for item in logs if item.get("lockevent") == 4),
                                None,
                            )
                            if last_unlock:
                                unlock_user = last_unlock.get("name")
                                unlock_type = last_unlock.get("type")
                                unlock_idx = str(last_unlock.get("index"))

                                # If name is empty, map from pin_users or action type
                                if not unlock_user:
                                    if unlock_type == 0 and unlock_idx in device_status.get("pin_users", {}):
                                        unlock_user = device_status["pin_users"][unlock_idx]
                                    elif unlock_type == 2:
                                        unlock_user = "Manual Operation"
                                    elif unlock_type == 103:
                                        unlock_user = "Alfred App"
                                    elif unlock_type == 104:
                                        unlock_user = "Auto Unlock"
                                    elif unlock_type == 105:
                                        unlock_user = "Remote (Bridge)"
                                    else:
                                        unlock_user = f"PIN #{unlock_idx}" if unlock_type == 0 else "Unknown"

                                device_status["last_unlocked_by"] = unlock_user
                                device_status["last_unlocked_time"] = last_unlock.get("time")
                                device_status["last_unlocked_type"] = unlock_type
                                device_status["last_unlocked_index"] = last_unlock.get("index")
                            else:
                                device_status["last_unlocked_by"] = None
                                device_status["last_unlocked_time"] = None
                        except Exception as log_err:
                            _LOGGER.debug("Could not fetch activity logs for %s: %s", lock_id, log_err)

                except Exception as detail_err:
                    _LOGGER.debug("Could not fetch lock detail for %s: %s", lock_id, detail_err)
                    # Preserve previous battery and user info if available
                    if self.data and lock_id in self.data:
                        for k in ("battery", "battery_time", "keypersons", "pin_users", "last_unlocked_by", "last_unlocked_time", "last_unlocked_type", "last_unlocked_index"):
                            device_status[k] = self.data[lock_id].get(k)

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
                        "battery": None,
                        "battery_time": None,
                        "keypersons": [],
                        "pin_users": {},
                        "last_unlocked_by": None,
                        "last_unlocked_time": None,
                        "malfunction": False,
                    }

        return status_data
