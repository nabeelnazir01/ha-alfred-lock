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

            entities.append(AlfredBleSignalSensor(coordinator, device, lock_id, master_id))

    async_add_entities(entities)


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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lock_id)},
            name=device.get("name", "Front Door"),
            manufacturer="Alfred International",
            model="DB2S Touchscreen Smart Lock",
            via_device=(DOMAIN, master_id) if master_id else None,
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
