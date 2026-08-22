"""Config flow for MyGarage."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import MyGarageApiClient, MyGarageApiError, MyGarageAuthError
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_WEBHOOK_TOKEN,
    CONF_WIDGET_API_KEY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="http://localhost:8686"): str,
        vol.Required(CONF_WIDGET_API_KEY): str,
        vol.Optional(CONF_WEBHOOK_TOKEN, default=""): str,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate connectivity and credentials."""
    client = MyGarageApiClient(
        data[CONF_URL],
        widget_api_key=data.get(CONF_WIDGET_API_KEY, ""),
        webhook_token=data.get(CONF_WEBHOOK_TOKEN, ""),
        username=data.get(CONF_USERNAME, ""),
        password=data.get(CONF_PASSWORD, ""),
    )
    try:
        health = await client.async_health()
        summary = await client.async_get_summary()
        if client.has_jwt_credentials:
            await client.async_login()
    finally:
        await client.close()

    version = (health or {}).get("version") or (health or {}).get("app") or "ok"
    return {"title": f"MyGarage ({version})"}


class MyGarageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyGarage."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            user_input[CONF_URL] = url
            await self.async_set_unique_id(url.lower())
            self._abort_if_unique_id_configured()
            try:
                info = await _validate_input(self.hass, user_input)
            except MyGarageAuthError:
                errors["base"] = "invalid_auth"
            except MyGarageApiError as err:
                _LOGGER.debug("Connection failed: %s", err)
                if err.status_code == 503:
                    errors["base"] = "webhook_not_configured"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MyGarageOptionsFlow:
        return MyGarageOptionsFlow()


class MyGarageOptionsFlow(config_entries.OptionsFlow):
    """Handle MyGarage options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_WIDGET_API_KEY,
                    default=data.get(CONF_WIDGET_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_WEBHOOK_TOKEN,
                    default=data.get(CONF_WEBHOOK_TOKEN, ""),
                ): str,
                vol.Optional(
                    CONF_USERNAME,
                    default=data.get(CONF_USERNAME, ""),
                ): str,
                vol.Optional(
                    CONF_PASSWORD,
                    default=data.get(CONF_PASSWORD, ""),
                ): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="seconds",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
