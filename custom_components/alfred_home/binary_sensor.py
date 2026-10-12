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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lock_id)},
            name=device.get("name", "Front Door"),
            manufacturer="Alfred International",
            model="DB2S Touchscreen Smart Lock",
            via_device=(DOMAIN, master_id) if master_id else None,
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lock_id)},
            name=device.get("name", "Front Door"),
            manufacturer="Alfred International",
            model="DB2S Touchscreen Smart Lock",
            via_device=(DOMAIN, master_id) if master_id else None,
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
