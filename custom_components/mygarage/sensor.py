"""Sensor platform for MyGarage."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import MyGarageCoordinator
from .entity import MyGarageEntity, MyGarageVehicleEntity

_SUMMARY_TOTAL = ("total_vehicles", "active_vehicles")
_SUMMARY_OVERDUE = ("total_overdue_maintenance", "overdue_maintenance")
_SUMMARY_UPCOMING = ("total_upcoming_maintenance", "upcoming_maintenance")


def _first_key(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MyGarage sensors."""
    coordinator: MyGarageCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[SensorEntity] = [
        MyGarageSummarySensor(
            coordinator, "total_vehicles", "Total vehicles", _SUMMARY_TOTAL,
            icon="mdi:car-multiple",
        ),
        MyGarageSummarySensor(
            coordinator, "overdue_maintenance", "Overdue maintenance",
            _SUMMARY_OVERDUE, icon="mdi:wrench-alert",
        ),
        MyGarageSummarySensor(
            coordinator, "upcoming_maintenance", "Upcoming maintenance",
            _SUMMARY_UPCOMING, icon="mdi:wrench-clock",
        ),
    ]

    known: set[str] = set()

    def _vehicle_entities(vin: str) -> list[SensorEntity]:
        ents: list[SensorEntity] = [
            MyGarageOdometerSensor(coordinator, vin),
            MyGarageFuelEconomySensor(coordinator, vin),
            MyGarageEngineHoursSensor(coordinator, vin),
            MyGarageVehicleCountSensor(
                coordinator, vin, "overdue_maintenance", "Overdue maintenance",
                ("overdue_maintenance",), icon="mdi:wrench-alert",
            ),
            MyGarageVehicleCountSensor(
                coordinator, vin, "upcoming_maintenance", "Upcoming maintenance",
                ("upcoming_maintenance",), icon="mdi:wrench-clock",
            ),
            MyGarageDateSensor(
                coordinator, vin, "last_service_date", "Last service",
                ("last_service_date",), icon="mdi:calendar-check",
            ),
            MyGarageDateSensor(
                coordinator, vin, "last_fuel_date", "Last fuel",
                ("last_fuel_date",), icon="mdi:gas-station",
            ),
            MyGarageLiveLinkBatterySensor(coordinator, vin),
            MyGarageLiveLinkRssiSensor(coordinator, vin),
            MyGaragePendingRemindersSensor(coordinator, vin),
            MyGarageNextReminderSensor(coordinator, vin),
            MyGarageActiveDtcCountSensor(coordinator, vin),
        ]
        bucket = coordinator.vehicle_data(vin) or {}
        livelink = bucket.get("livelink") or {}
        for item in livelink.get("latest_values") or []:
            key = item.get("param_key") or item.get("key")
            if key:
                ents.append(MyGarageTelemetrySensor(coordinator, vin, str(key)))
        return ents

    for vin in coordinator.vehicle_vins():
        known.add(vin)
        entities.extend(_vehicle_entities(vin))

    async_add_entities(entities)

    @callback
    def _check_new_vehicles() -> None:
        new_vins = [v for v in coordinator.vehicle_vins() if v not in known]
        if not new_vins:
            return
        added: list[SensorEntity] = []
        for vin in new_vins:
            known.add(vin)
            added.extend(_vehicle_entities(vin))
        if added:
            async_add_entities(added)

    entry.async_on_unload(coordinator.async_add_listener(_check_new_vehicles))


class MyGarageSummarySensor(MyGarageEntity, SensorEntity):
    """Garage-level summary count."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: MyGarageCoordinator,
        key: str,
        name: str,
        fields: tuple[str, ...],
        *,
        icon: str,
    ) -> None:
        super().__init__(coordinator, key)
        self._fields = fields
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self) -> int | None:
        value = _first_key(self.coordinator.summary(), self._fields)
        return int(value) if value is not None else None


class MyGarageOdometerSensor(MyGarageVehicleEntity, SensorEntity):
    """Vehicle odometer."""

    _attr_name = "Odometer"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "odometer")

    @property
    def native_unit_of_measurement(self) -> str:
        if self.hass.config.units.is_metric:
            return UnitOfLength.KILOMETERS
        return UnitOfLength.MILES

    @property
    def native_value(self) -> int | None:
        widget = self.widget
        if self.hass.config.units.is_metric:
            value = widget.get("odometer_km", widget.get("odometer"))
        else:
            value = widget.get("odometer", widget.get("odometer_km"))
        return int(value) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "odometer_date": self.widget.get("odometer_date"),
            "odometer_km": self.widget.get("odometer_km"),
            "odometer_mi": self.widget.get("odometer"),
        }


class MyGarageFuelEconomySensor(MyGarageVehicleEntity, SensorEntity):
    """Recent fuel economy."""

    _attr_name = "Fuel economy"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "fuel_economy")

    @property
    def native_unit_of_measurement(self) -> str:
        return "L/100km" if self.hass.config.units.is_metric else "mpg"

    @property
    def native_value(self) -> float | None:
        widget = self.widget
        if self.hass.config.units.is_metric:
            value = widget.get("recent_l_per_100km", widget.get("average_l_per_100km"))
        else:
            value = widget.get("recent_mpg", widget.get("average_mpg"))
        return float(value) if value is not None else None


class MyGarageEngineHoursSensor(MyGarageVehicleEntity, SensorEntity):
    """Engine hours when tracked."""

    _attr_name = "Engine hours"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = "h"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "engine_hours")

    @property
    def native_value(self) -> float | None:
        value = self.widget.get("latest_hours")
        return float(value) if value is not None else None

    @property
    def available(self) -> bool:
        return super().available and self.widget.get("latest_hours") is not None


class MyGarageVehicleCountSensor(MyGarageVehicleEntity, SensorEntity):
    """Integer count from widget payload."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: MyGarageCoordinator,
        vin: str,
        key: str,
        name: str,
        fields: tuple[str, ...],
        *,
        icon: str,
    ) -> None:
        super().__init__(coordinator, vin, key)
        self._fields = fields
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self) -> int | None:
        value = _first_key(self.widget, self._fields)
        return int(value) if value is not None else None


class MyGarageDateSensor(MyGarageVehicleEntity, SensorEntity):
    """Date from widget payload."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self,
        coordinator: MyGarageCoordinator,
        vin: str,
        key: str,
        name: str,
        fields: tuple[str, ...],
        *,
        icon: str,
    ) -> None:
        super().__init__(coordinator, vin, key)
        self._fields = fields
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self) -> date | None:
        value = _first_key(self.widget, self._fields)
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        parsed = dt_util.parse_datetime(str(value))
        if parsed:
            return parsed.date()
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


class MyGarageLiveLinkBatterySensor(MyGarageVehicleEntity, SensorEntity):
    """LiveLink battery voltage."""

    _attr_name = "LiveLink battery"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "V"
    _attr_icon = "mdi:car-battery"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "livelink_battery")

    @property
    def available(self) -> bool:
        return super().available and bool(self.livelink)

    @property
    def native_value(self) -> float | None:
        value = self.livelink.get("battery_voltage")
        return float(value) if value is not None else None


class MyGarageLiveLinkRssiSensor(MyGarageVehicleEntity, SensorEntity):
    """LiveLink Wi-Fi RSSI."""

    _attr_name = "LiveLink RSSI"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "livelink_rssi")

    @property
    def available(self) -> bool:
        return super().available and bool(self.livelink)

    @property
    def native_value(self) -> int | None:
        value = self.livelink.get("rssi")
        return int(value) if value is not None else None


class MyGarageTelemetrySensor(MyGarageVehicleEntity, SensorEntity):
    """Dynamic LiveLink telemetry reading."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: MyGarageCoordinator, vin: str, param_key: str
    ) -> None:
        super().__init__(coordinator, vin, f"telemetry_{param_key}")
        self._param_key = param_key
        self._attr_name = param_key.replace("_", " ").title()
        self._attr_icon = "mdi:car-info"

    def _reading(self) -> dict[str, Any] | None:
        for item in self.livelink.get("latest_values") or []:
            key = item.get("param_key") or item.get("key")
            if key == self._param_key:
                return item
        return None

    @property
    def available(self) -> bool:
        return super().available and self._reading() is not None

    @property
    def native_value(self) -> float | None:
        reading = self._reading()
        if not reading:
            return None
        value = reading.get("value")
        return float(value) if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        reading = self._reading()
        return None if not reading else reading.get("unit")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        reading = self._reading() or {}
        return {
            "display_name": reading.get("display_name"),
            "timestamp": reading.get("timestamp"),
            "in_warning": reading.get("in_warning"),
        }


class MyGaragePendingRemindersSensor(MyGarageVehicleEntity, SensorEntity):
    """Count of pending reminders."""

    _attr_name = "Pending reminders"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:bell-badge"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "pending_reminders")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.has_jwt_credentials

    @property
    def native_value(self) -> int:
        return len(self.reminders)


class MyGarageNextReminderSensor(MyGarageVehicleEntity, SensorEntity):
    """Next pending reminder title."""

    _attr_name = "Next reminder"
    _attr_icon = "mdi:bell-ring"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "next_reminder")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.has_jwt_credentials

    @property
    def native_value(self) -> str | None:
        if not self.reminders:
            return None
        first = self.reminders[0]
        return first.get("title") or first.get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.reminders:
            return {}
        first = self.reminders[0]
        return {
            "reminder_id": first.get("id"),
            "due_date": first.get("due_date"),
            "due_mileage_km": first.get("due_mileage_km"),
            "reminder_type": first.get("reminder_type"),
            "status": first.get("status"),
        }


class MyGarageActiveDtcCountSensor(MyGarageVehicleEntity, SensorEntity):
    """Active DTC count."""

    _attr_name = "Active DTCs"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:engine-off"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "active_dtc_count")

    @property
    def available(self) -> bool:
        return super().available and bool(self.dtcs)

    @property
    def native_value(self) -> int | None:
        if "active_count" in self.dtcs:
            return int(self.dtcs["active_count"])
        return len(self.dtcs.get("dtcs") or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        codes = self.dtcs.get("dtcs") or []
        return {
            "codes": [c.get("code") for c in codes[:10] if isinstance(c, dict)],
            "critical_count": self.dtcs.get("critical_count"),
        }
