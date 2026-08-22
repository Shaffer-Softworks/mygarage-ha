"""Data update coordinator for MyGarage."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyGarageApiClient, MyGarageApiError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MyGarageCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll widget (+ optional JWT) endpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MyGarageApiClient,
    ) -> None:
        interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=int(interval)),
            config_entry=entry,
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            summary = await self.client.async_get_summary()
            vehicle_refs = await self.client.async_list_vehicles()
        except MyGarageApiError as err:
            raise UpdateFailed(str(err)) from err

        vehicles: dict[str, dict[str, Any]] = {}
        for ref in vehicle_refs:
            vin = (ref.get("vin") or "").upper()
            if not vin:
                continue
            try:
                detail = await self.client.async_get_vehicle(vin)
            except MyGarageApiError as err:
                _LOGGER.warning("Failed to fetch vehicle %s: %s", vin, err)
                detail = {}
            vehicles[vin] = {
                "ref": ref,
                "widget": detail,
                "livelink": None,
                "dtcs": None,
                "reminders": [],
            }

        if self.client.has_jwt_credentials:
            for vin, bucket in vehicles.items():
                try:
                    bucket["livelink"] = await self.client.async_get_livelink_status(
                        vin
                    )
                except MyGarageApiError as err:
                    _LOGGER.debug("LiveLink unavailable for %s: %s", vin, err)
                try:
                    bucket["dtcs"] = await self.client.async_list_dtcs(vin)
                except MyGarageApiError as err:
                    _LOGGER.debug("DTCs unavailable for %s: %s", vin, err)
                try:
                    bucket["reminders"] = await self.client.async_list_reminders(vin)
                except MyGarageApiError as err:
                    _LOGGER.debug("Reminders unavailable for %s: %s", vin, err)

        return {"summary": summary or {}, "vehicles": vehicles}

    def vehicle_vins(self) -> list[str]:
        if not self.data:
            return []
        return list(self.data.get("vehicles", {}).keys())

    def vehicle_data(self, vin: str) -> dict[str, Any] | None:
        if not self.data:
            return None
        return self.data.get("vehicles", {}).get(vin.upper())

    def summary(self) -> dict[str, Any]:
        if not self.data:
            return {}
        return self.data.get("summary") or {}
