"""Binary sensor platform for MyGarage."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MyGarageCoordinator
from .entity import MyGarageVehicleEntity

_MAX_DTC_ENTITIES = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MyGarage binary sensors."""
    coordinator: MyGarageCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    known: set[str] = set()
    known_dtc_keys: set[str] = set()

    def _vehicle_entities(vin: str) -> list[BinarySensorEntity]:
        ents: list[BinarySensorEntity] = [
            MyGarageMaintenanceOverdueBinarySensor(coordinator, vin),
            MyGarageLiveLinkOnlineBinarySensor(coordinator, vin),
            MyGarageEcuOnlineBinarySensor(coordinator, vin),
            MyGarageSessionActiveBinarySensor(coordinator, vin),
            MyGarageActiveDtcBinarySensor(coordinator, vin),
        ]
        bucket = coordinator.vehicle_data(vin) or {}
        dtcs = bucket.get("dtcs") or {}
        codes = list(dtcs.get("dtcs") or [])[:_MAX_DTC_ENTITIES]
        for dtc in codes:
            if not isinstance(dtc, dict):
                continue
            code = dtc.get("code")
            if not code:
                continue
            key = f"{vin}:{code}"
            if key in known_dtc_keys:
                continue
            known_dtc_keys.add(key)
            ents.append(MyGarageDtcCodeBinarySensor(coordinator, vin, str(code)))
        return ents

    entities: list[BinarySensorEntity] = []
    for vin in coordinator.vehicle_vins():
        known.add(vin)
        entities.extend(_vehicle_entities(vin))

    async_add_entities(entities)

    @callback
    def _check_new() -> None:
        added: list[BinarySensorEntity] = []
        for vin in coordinator.vehicle_vins():
            if vin not in known:
                known.add(vin)
                added.extend(_vehicle_entities(vin))
            else:
                # Pick up newly reported DTC codes
                bucket = coordinator.vehicle_data(vin) or {}
                dtcs = bucket.get("dtcs") or {}
                codes = list(dtcs.get("dtcs") or [])[:_MAX_DTC_ENTITIES]
                for dtc in codes:
                    if not isinstance(dtc, dict):
                        continue
                    code = dtc.get("code")
                    if not code:
                        continue
                    key = f"{vin}:{code}"
                    if key in known_dtc_keys:
                        continue
                    known_dtc_keys.add(key)
                    added.append(
                        MyGarageDtcCodeBinarySensor(coordinator, vin, str(code))
                    )
        if added:
            async_add_entities(added)

    entry.async_on_unload(coordinator.async_add_listener(_check_new))


class MyGarageMaintenanceOverdueBinarySensor(MyGarageVehicleEntity, BinarySensorEntity):
    """True when vehicle has overdue maintenance."""

    _attr_name = "Maintenance overdue"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:wrench-alert"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "maintenance_overdue")

    @property
    def is_on(self) -> bool:
        value = self.widget.get("overdue_maintenance") or 0
        return int(value) > 0


class MyGarageLiveLinkOnlineBinarySensor(MyGarageVehicleEntity, BinarySensorEntity):
    """True when LiveLink device is online."""

    _attr_name = "LiveLink online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "livelink_online")

    @property
    def available(self) -> bool:
        return super().available and bool(self.livelink)

    @property
    def is_on(self) -> bool:
        return str(self.livelink.get("device_status", "")).lower() == "online"


class MyGarageEcuOnlineBinarySensor(MyGarageVehicleEntity, BinarySensorEntity):
    """True when ECU is online."""

    _attr_name = "ECU online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:engine"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "ecu_online")

    @property
    def available(self) -> bool:
        return super().available and bool(self.livelink)

    @property
    def is_on(self) -> bool:
        return str(self.livelink.get("ecu_status", "")).lower() == "online"


class MyGarageSessionActiveBinarySensor(MyGarageVehicleEntity, BinarySensorEntity):
    """True when a LiveLink drive session is active."""

    _attr_name = "Session active"
    _attr_icon = "mdi:car-connected"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "session_active")

    @property
    def available(self) -> bool:
        return super().available and bool(self.livelink)

    @property
    def is_on(self) -> bool:
        return self.livelink.get("current_session_id") is not None


class MyGarageActiveDtcBinarySensor(MyGarageVehicleEntity, BinarySensorEntity):
    """True when any active DTC is present."""

    _attr_name = "Active DTC"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:engine-off"

    def __init__(self, coordinator: MyGarageCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "active_dtc")

    @property
    def available(self) -> bool:
        return super().available and bool(self.dtcs)

    @property
    def is_on(self) -> bool:
        if "active_count" in self.dtcs:
            return int(self.dtcs["active_count"] or 0) > 0
        return len(self.dtcs.get("dtcs") or []) > 0


class MyGarageDtcCodeBinarySensor(MyGarageVehicleEntity, BinarySensorEntity):
    """Per-code DTC binary sensor (capped)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-octagon"

    def __init__(
        self, coordinator: MyGarageCoordinator, vin: str, code: str
    ) -> None:
        super().__init__(coordinator, vin, f"dtc_{code}")
        self._code = code
        self._attr_name = f"DTC {code}"

    def _match(self) -> dict | None:
        for dtc in self.dtcs.get("dtcs") or []:
            if isinstance(dtc, dict) and dtc.get("code") == self._code:
                return dtc
        return None

    @property
    def available(self) -> bool:
        return super().available and bool(self.dtcs)

    @property
    def is_on(self) -> bool:
        match = self._match()
        if not match:
            return False
        if "is_active" in match:
            return bool(match["is_active"])
        return True

    @property
    def extra_state_attributes(self) -> dict:
        match = self._match() or {}
        return {
            "description": match.get("description"),
            "severity": match.get("severity"),
            "first_seen": match.get("first_seen"),
            "last_seen": match.get("last_seen"),
        }
