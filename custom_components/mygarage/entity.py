"""Shared entity helpers for MyGarage."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyGarageCoordinator


class MyGarageEntity(CoordinatorEntity[MyGarageCoordinator]):
    """Base entity for garage-level devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MyGarageCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=self.coordinator.entry.title or "MyGarage",
            manufacturer="homelabforge",
            model="MyGarage",
            configuration_url=self.coordinator.client.base_url,
        )


class MyGarageVehicleEntity(CoordinatorEntity[MyGarageCoordinator]):
    """Base entity tied to a MyGarage vehicle (VIN)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MyGarageCoordinator, vin: str, key: str
    ) -> None:
        super().__init__(coordinator)
        self._vin = vin.upper()
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{self._vin}_{key}"

    @property
    def vehicle_bucket(self) -> dict | None:
        return self.coordinator.vehicle_data(self._vin)

    @property
    def widget(self) -> dict:
        return (self.vehicle_bucket or {}).get("widget") or {}

    @property
    def livelink(self) -> dict:
        return (self.vehicle_bucket or {}).get("livelink") or {}

    @property
    def dtcs(self) -> dict:
        return (self.vehicle_bucket or {}).get("dtcs") or {}

    @property
    def reminders(self) -> list:
        return list((self.vehicle_bucket or {}).get("reminders") or [])

    @property
    def label(self) -> str:
        ref = (self.vehicle_bucket or {}).get("ref") or {}
        return ref.get("label") or self.widget.get("label") or self._vin

    @property
    def device_info(self) -> DeviceInfo:
        widget = self.widget
        make = widget.get("make") or "MyGarage"
        year = widget.get("year")
        model = widget.get("model") or "Vehicle"
        model_parts = [str(p) for p in (year, model) if p]
        return DeviceInfo(
            identifiers={(DOMAIN, f"vin_{self._vin}")},
            name=self.label,
            manufacturer=make,
            model=" ".join(model_parts) if model_parts else "Vehicle",
            serial_number=self._vin,
            via_device=(DOMAIN, self.coordinator.entry.entry_id),
            configuration_url=self.coordinator.client.base_url,
        )

    @property
    def available(self) -> bool:
        return super().available and self.vehicle_bucket is not None
