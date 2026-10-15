"""Support for Alfred door sensors and connectivity binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AlfredDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfred binary sensors based on a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AlfredDataUpdateCoordinator = entry_data["coordinator"]
    devices: list[dict[str, Any]] = entry_data["devices"]

    entities: list[BinarySensorEntity] = []

    for device in devices:
        if device.get("isLock"):
            lock_id = device["deviceId"]
            master_id = device.get("masterId")

            # Check if door sensor capability is supported by this lock hardware
            lock_status = coordinator.data.get(lock_id, {}) if coordinator.data else {}
            has_doorsensor = device.get("has_doorsensor") or lock_status.get("has_doorsensor", False)

            if has_doorsensor:
                entities.append(AlfredDoorSensor(coordinator, device, lock_id, master_id))

            entities.append(AlfredBleConnectivitySensor(coordinator, device, lock_id, master_id))

    async_add_entities(entities)


class AlfredDoorSensor(CoordinatorEntity[AlfredDataUpdateCoordinator], BinarySensorEntity):
    """Door opening/closing contact sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "door_sensor"
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self,
        coordinator: AlfredDataUpdateCoordinator,
        device: dict[str, Any],
        lock_id: str,
        master_id: str | None,
    ) -> None:
        """Initialize door sensor entity."""
        super().__init__(coordinator)
        self.lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{lock_id}_door_sensor"
        self._attr_name = "Door"
        self.device = device
        self.master_id = master_id

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
    def is_on(self) -> bool | None:
        """Return True if door is open, False if closed."""
        if not self.coordinator.data:
            return False
        status = self.coordinator.data.get(self.lock_id, {})
        return status.get("door_sensor_open", False)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data and self.lock_id in self.coordinator.data)


class AlfredBleConnectivitySensor(CoordinatorEntity[AlfredDataUpdateCoordinator], BinarySensorEntity):
    """Bridge Bluetooth connection status to door lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "bridge_ble_link"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: AlfredDataUpdateCoordinator,
        device: dict[str, Any],
        lock_id: str,
        master_id: str | None,
    ) -> None:
        """Initialize BLE link connectivity entity."""
        super().__init__(coordinator)
        self.lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{lock_id}_ble_link"
        self._attr_name = "Bridge BLE Link"
        self.device = device
        self.master_id = master_id

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
    def is_on(self) -> bool | None:
        """Return True if bridge is actively connected to lock over BLE."""
        if not self.coordinator.data:
            return True
        status = self.coordinator.data.get(self.lock_id, {})
        return status.get("lock_online", True)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data and self.lock_id in self.coordinator.data)
