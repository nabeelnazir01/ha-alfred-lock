"""Support for Alfred BLE Signal sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
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
    """Set up Alfred sensors based on a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AlfredDataUpdateCoordinator = entry_data["coordinator"]
    devices: list[dict[str, Any]] = entry_data["devices"]

    entities: list[SensorEntity] = []

    for device in devices:
        if device.get("isLock"):
            lock_id = device["deviceId"]
            master_id = device.get("masterId")

            entities.append(AlfredBatterySensor(coordinator, device, lock_id, master_id))
            entities.append(AlfredLastUnlockedBySensor(coordinator, device, lock_id, master_id))
            entities.append(AlfredBleSignalSensor(coordinator, device, lock_id, master_id))

    async_add_entities(entities)


class AlfredLastUnlockedBySensor(CoordinatorEntity[AlfredDataUpdateCoordinator], SensorEntity):
    """Sensor reporting the name of the user or method that last unlocked the lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_unlocked_by"
    _attr_icon = "mdi:account-key"

    def __init__(
        self,
        coordinator: AlfredDataUpdateCoordinator,
        device: dict[str, Any],
        lock_id: str,
        master_id: str | None,
    ) -> None:
        """Initialize Last Unlocked By sensor."""
        super().__init__(coordinator)
        self.lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{lock_id}_last_unlocked_by"
        self._attr_name = "Last Unlocked By"
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
    def native_value(self) -> str | None:
        """Return the user profile name or method that unlocked the door."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get(self.lock_id, {})
        return status.get("last_unlocked_by")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return registered PIN user profiles and event metadata."""
        attrs: dict[str, Any] = {}
        if self.coordinator.data and self.lock_id in self.coordinator.data:
            lock_data = self.coordinator.data[self.lock_id]
            if lock_data.get("last_unlocked_time"):
                attrs["last_unlocked_timestamp"] = lock_data["last_unlocked_time"]
            if lock_data.get("last_unlocked_type") is not None:
                attrs["last_unlocked_type"] = lock_data["last_unlocked_type"]
            if lock_data.get("last_unlocked_index") is not None:
                attrs["last_unlocked_pin_slot"] = lock_data["last_unlocked_index"]
            if lock_data.get("pin_users"):
                attrs["registered_user_profiles"] = lock_data["pin_users"]
        return attrs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data and self.lock_id in self.coordinator.data)


class AlfredBatterySensor(CoordinatorEntity[AlfredDataUpdateCoordinator], SensorEntity):
    """Battery percentage sensor for Alfred Smart Lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AlfredDataUpdateCoordinator,
        device: dict[str, Any],
        lock_id: str,
        master_id: str | None,
    ) -> None:
        """Initialize Battery sensor."""
        super().__init__(coordinator)
        self.lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{lock_id}_battery"
        self._attr_name = "Battery"
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
    def native_value(self) -> int | None:
        """Return the battery level in percentage (0-100)."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get(self.lock_id, {})
        return status.get("battery")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for battery."""
        attrs: dict[str, Any] = {}
        if self.coordinator.data and self.lock_id in self.coordinator.data:
            battery_ts = self.coordinator.data[self.lock_id].get("battery_time")
            if battery_ts:
                attrs["battery_updated_timestamp"] = battery_ts
        return attrs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data and self.lock_id in self.coordinator.data)


class AlfredBleSignalSensor(CoordinatorEntity[AlfredDataUpdateCoordinator], SensorEntity):
    """Bluetooth Signal Strength sensor between Wi-Fi Bridge and Lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "ble_signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AlfredDataUpdateCoordinator,
        device: dict[str, Any],
        lock_id: str,
        master_id: str | None,
    ) -> None:
        """Initialize BLE signal sensor."""
        super().__init__(coordinator)
        self.lock_id = lock_id
        self._attr_unique_id = f"{DOMAIN}_{lock_id}_ble_signal"
        self._attr_name = "BLE Signal"
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
    def native_value(self) -> int | None:
        """Return the BLE signal strength in dBm."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get(self.lock_id, {})
        return status.get("ble_signal")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data and self.lock_id in self.coordinator.data)
