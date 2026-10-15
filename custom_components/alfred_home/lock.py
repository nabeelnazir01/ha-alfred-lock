"""Support for Alfred Smart Locks in Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .alfred_api import AlfredApiClient, AlfredDeviceTimeout
from .const import DOMAIN
from .coordinator import AlfredDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfred lock entities based on a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    client: AlfredApiClient = entry_data["client"]
    coordinator: AlfredDataUpdateCoordinator = entry_data["coordinator"]
    devices: list[dict[str, Any]] = entry_data["devices"]

    entities: list[AlfredLockEntity] = []

    for device in devices:
        if device.get("isLock"):
            master_id = device.get("masterId")
            if not master_id:
                bridge = next((d for d in devices if d.get("isBridge")), None)
                master_id = bridge["deviceId"] if bridge else "G3B9BMOWNI2D0XT9"

            entities.append(
                AlfredLockEntity(
                    coordinator=coordinator,
                    client=client,
                    device=device,
                    master_id=master_id,
                )
            )

    async_add_entities(entities)


class AlfredLockEntity(CoordinatorEntity[AlfredDataUpdateCoordinator], LockEntity):
    """Representation of an Alfred Smart Lock."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = LockEntityFeature(0)

    def __init__(
        self,
        coordinator: AlfredDataUpdateCoordinator,
        client: AlfredApiClient,
        device: dict[str, Any],
        master_id: str,
    ) -> None:
        """Initialize the lock entity."""
        super().__init__(coordinator)
        self.client = client
        self.device = device
        self.lock_id = device["deviceId"]
        self.master_id = master_id

        self._attr_unique_id = f"{DOMAIN}_{self.lock_id}"
        self._is_locking = False
        self._is_unlocking = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return dynamic device information for this lock."""
        status = self.coordinator.data.get(self.lock_id, {}) if self.coordinator.data else {}
        model_name = status.get("model") or self.device.get("model") or "DB1 Touchscreen Smart Lock"
        if not model_name.endswith("Smart Lock") and not "Lock" in model_name:
            model_name = f"{model_name} Touchscreen Smart Lock"
        sw_version = status.get("fw_version") or self.device.get("fw_version")

        return DeviceInfo(
            identifiers={(DOMAIN, self.lock_id)},
            name=self.device.get("name", "Front Door"),
            manufacturer="Alfred International",
            model=model_name,
            sw_version=sw_version,
            via_device=(DOMAIN, self.master_id) if self.master_id else None,
        )

    @property
    def is_locked(self) -> bool:
        """Return True if the lock is currently locked."""
        if not self.coordinator.data:
            return True
        status = self.coordinator.data.get(self.lock_id, {})
        return status.get("is_locked", True)

    @property
    def is_locking(self) -> bool:
        """Return True if the lock is currently locking."""
        return self._is_locking

    @property
    def is_unlocking(self) -> bool:
        """Return True if the lock is currently unlocking."""
        return self._is_unlocking

    @property
    def available(self) -> bool:
        """Return True if the entity is available in Home Assistant."""
        if not self.coordinator.last_update_success:
            return False
        return bool(self.coordinator.data and self.lock_id in self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic state attributes."""
        if not self.coordinator.data:
            return {}
        status = self.coordinator.data.get(self.lock_id, {})
        return {
            "bridge_id": self.master_id,
            "bridge_online": status.get("bridge_online", False),
            "lock_ble_connected": status.get("lock_online", False),
            "ble_signal_dbm": status.get("ble_signal"),
            "door_sensor_open": status.get("door_sensor_open", False),
            "last_unlocked_by": status.get("last_unlocked_by"),
            "registered_user_profiles": status.get("pin_users"),
            "malfunction": status.get("malfunction", False),
        }

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door."""
        self._is_locking = True
        self.async_write_ha_state()

        try:
            await self.client.operate_lock(
                lock_id=self.lock_id,
                bridge_id=self.master_id,
                lock=True,
            )
            # Update coordinator state immediately
            if self.coordinator.data and self.lock_id in self.coordinator.data:
                self.coordinator.data[self.lock_id]["is_locked"] = True
        except AlfredDeviceTimeout as err:
            _LOGGER.error("Lock timeout for %s: %s", self.name, err)
            raise
        except Exception as err:
            _LOGGER.error("Failed to lock %s: %s", self.name, err)
            raise
        finally:
            self._is_locking = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        self._is_unlocking = True
        self.async_write_ha_state()

        try:
            await self.client.operate_lock(
                lock_id=self.lock_id,
                bridge_id=self.master_id,
                lock=False,
            )
            # Update coordinator state immediately
            if self.coordinator.data and self.lock_id in self.coordinator.data:
                self.coordinator.data[self.lock_id]["is_locked"] = False
        except AlfredDeviceTimeout as err:
            _LOGGER.error("Unlock timeout for %s: %s", self.name, err)
            raise
        except Exception as err:
            _LOGGER.error("Failed to unlock %s: %s", self.name, err)
            raise
        finally:
            self._is_unlocking = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
