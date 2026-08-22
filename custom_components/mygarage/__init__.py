"""The MyGarage Home Assistant integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import MyGarageApiClient, MyGarageApiError
from .const import (
    ATTR_VIN,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_WEBHOOK_TOKEN,
    CONF_WIDGET_API_KEY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_COMPLETE_REMINDER,
    SERVICE_LOG_FUEL,
    SERVICE_LOG_ODOMETER,
)
from .coordinator import MyGarageCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

SERVICE_LOG_FUEL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VIN): cv.string,
        vol.Optional("odometer_km"): vol.Coerce(float),
        vol.Optional("liters"): vol.Coerce(float),
        vol.Optional("kwh"): vol.Coerce(float),
        vol.Optional("cost"): vol.Coerce(float),
        vol.Optional("price_per_unit"): vol.Coerce(float),
        vol.Optional("is_full_tank", default=True): cv.boolean,
        vol.Optional("notes"): cv.string,
        vol.Optional("date"): cv.string,
    }
)

SERVICE_LOG_ODOMETER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VIN): cv.string,
        vol.Required("odometer_km"): vol.Coerce(float),
        vol.Optional("notes"): cv.string,
        vol.Optional("date"): cv.string,
    }
)

SERVICE_COMPLETE_REMINDER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VIN): cv.string,
        vol.Required("reminder_id"): vol.Coerce(int),
    }
)


def _merged_config(entry: ConfigEntry) -> dict:
    return {**entry.data, **entry.options}


def _build_client(entry: ConfigEntry) -> MyGarageApiClient:
    cfg = _merged_config(entry)
    return MyGarageApiClient(
        cfg[CONF_URL],
        widget_api_key=cfg.get(CONF_WIDGET_API_KEY, ""),
        webhook_token=cfg.get(CONF_WEBHOOK_TOKEN, ""),
        username=cfg.get(CONF_USERNAME, ""),
        password=cfg.get(CONF_PASSWORD, ""),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyGarage from a config entry."""
    client = _build_client(entry)
    coordinator = MyGarageCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        stored = hass.data[DOMAIN].pop(entry.entry_id, None)
        if stored and stored.get("client"):
            await stored["client"].close()
        if not hass.data[DOMAIN]:
            for service in (
                SERVICE_LOG_FUEL,
                SERVICE_LOG_ODOMETER,
                SERVICE_COMPLETE_REMINDER,
            ):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options / data updates."""
    stored = hass.data[DOMAIN].get(entry.entry_id)
    if not stored:
        return
    old_client: MyGarageApiClient = stored["client"]
    await old_client.close()
    client = _build_client(entry)
    coordinator: MyGarageCoordinator = stored["coordinator"]
    coordinator.client = client
    stored["client"] = client
    interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    coordinator.update_interval = timedelta(seconds=int(interval))
    await coordinator.async_request_refresh()


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_LOG_FUEL):
        return

    def _first_client() -> MyGarageApiClient:
        for stored in hass.data.get(DOMAIN, {}).values():
            return stored["client"]
        raise HomeAssistantError("MyGarage is not configured")

    async def _handle_log_fuel(call: ServiceCall) -> None:
        client = _first_client()
        if not client.has_webhook:
            raise ServiceValidationError(
                "Webhook token is not configured for MyGarage"
            )
        data = dict(call.data)
        data["vin"] = str(data.pop(ATTR_VIN)).upper()
        try:
            await client.async_webhook_fuel(data)
        except MyGarageApiError as err:
            raise HomeAssistantError(str(err)) from err

    async def _handle_log_odometer(call: ServiceCall) -> None:
        client = _first_client()
        if not client.has_webhook:
            raise ServiceValidationError(
                "Webhook token is not configured for MyGarage"
            )
        payload = {
            "vin": str(call.data[ATTR_VIN]).upper(),
            "odometer_km": call.data["odometer_km"],
        }
        if "notes" in call.data:
            payload["notes"] = call.data["notes"]
        if "date" in call.data:
            payload["date"] = call.data["date"]
        try:
            await client.async_webhook_odometer(payload)
        except MyGarageApiError as err:
            raise HomeAssistantError(str(err)) from err

    async def _handle_complete_reminder(call: ServiceCall) -> None:
        client = _first_client()
        if not client.has_webhook:
            raise ServiceValidationError(
                "Webhook token is not configured for MyGarage"
            )
        try:
            await client.async_webhook_complete_reminder(
                str(call.data[ATTR_VIN]).upper(),
                int(call.data["reminder_id"]),
            )
        except MyGarageApiError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN, SERVICE_LOG_FUEL, _handle_log_fuel, schema=SERVICE_LOG_FUEL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_ODOMETER,
        _handle_log_odometer,
        schema=SERVICE_LOG_ODOMETER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_REMINDER,
        _handle_complete_reminder,
        schema=SERVICE_COMPLETE_REMINDER_SCHEMA,
    )
