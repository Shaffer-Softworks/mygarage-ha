"""Async HTTP client for the MyGarage API."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = ClientTimeout(total=20, sock_connect=10)


class MyGarageApiError(Exception):
    """Raised when the MyGarage API returns an error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MyGarageAuthError(MyGarageApiError):
    """Raised for authentication failures."""


class MyGarageApiClient:
    """aiohttp client covering widget, webhook, and JWT REST surfaces."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        *,
        widget_api_key: str = "",
        webhook_token: str = "",
        username: str = "",
        password: str = "",
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._widget_api_key = widget_api_key.strip()
        self._webhook_token = webhook_token.strip()
        self._username = username.strip()
        self._password = password
        self._jwt: str | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def has_webhook(self) -> bool:
        return bool(self._webhook_token)

    @property
    def has_jwt_credentials(self) -> bool:
        return bool(self._username and self._password)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_auth: bool = False,
    ) -> Any:
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers=req_headers,
                json=json_data,
                params=params,
                timeout=_TIMEOUT,
            ) as response:
                status = response.status
                text = await response.text()
        except ClientError as err:
            raise MyGarageApiError(str(err)) from err

        if status == 401 and retry_auth and self.has_jwt_credentials:
            await self.async_login()
            headers = dict(headers or {})
            headers["Authorization"] = f"Bearer {self._jwt}"
            return await self._request(
                method,
                path,
                headers=headers,
                json_data=json_data,
                params=params,
                retry_auth=False,
            )

        if status in (401, 403):
            raise MyGarageAuthError(
                f"Unauthorized: {text}", status_code=status
            )
        if status >= 400:
            raise MyGarageApiError(
                f"{status}: {text}",
                status_code=status,
            )
        if status == 204 or not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise MyGarageApiError(f"Invalid JSON response: {err}") from err

    async def async_health(self) -> dict[str, Any]:
        """Probe connectivity via /health or /api/health."""
        try:
            return await self._request("GET", "/health")
        except MyGarageApiError:
            return await self._request("GET", "/api/health")

    # ------------------------------------------------------------------
    # Widget API (X-API-Key)
    # ------------------------------------------------------------------

    def _widget_headers(self) -> dict[str, str]:
        if not self._widget_api_key:
            raise MyGarageAuthError("Widget API key is not configured")
        return {"X-API-Key": self._widget_api_key}

    async def async_get_summary(self) -> dict[str, Any]:
        return await self._request(
            "GET", "/api/v2/widget/summary", headers=self._widget_headers()
        )

    async def async_list_vehicles(self) -> list[dict[str, Any]]:
        data = await self._request(
            "GET", "/api/v2/widget/vehicles", headers=self._widget_headers()
        )
        if isinstance(data, dict):
            return list(data.get("vehicles") or [])
        return list(data or [])

    async def async_get_vehicle(self, vin: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v2/widget/vehicle/{vin.upper()}",
            headers=self._widget_headers(),
        )

    # ------------------------------------------------------------------
    # Webhooks (X-Webhook-Token)
    # ------------------------------------------------------------------

    def _webhook_headers(self) -> dict[str, str]:
        if not self._webhook_token:
            raise MyGarageApiError(
                "Webhook token is not configured", status_code=503
            )
        return {"X-Webhook-Token": self._webhook_token}

    async def async_webhook_fuel(self, payload: dict[str, Any]) -> Any:
        return await self._request(
            "POST",
            "/api/v1/webhooks/fuel",
            headers=self._webhook_headers(),
            json_data=payload,
        )

    async def async_webhook_odometer(self, payload: dict[str, Any]) -> Any:
        return await self._request(
            "POST",
            "/api/v1/webhooks/odometer",
            headers=self._webhook_headers(),
            json_data=payload,
        )

    async def async_webhook_complete_reminder(
        self, vin: str, reminder_id: int
    ) -> Any:
        return await self._request(
            "POST",
            "/api/v1/webhooks/reminders/complete",
            headers=self._webhook_headers(),
            json_data={"vin": vin, "reminder_id": reminder_id},
        )

    # ------------------------------------------------------------------
    # JWT REST (LiveLink + reminders)
    # ------------------------------------------------------------------

    async def async_login(self) -> str:
        if not self.has_jwt_credentials:
            raise MyGarageAuthError("Username/password not configured")
        data = await self._request(
            "POST",
            "/api/auth/login",
            json_data={"username": self._username, "password": self._password},
        )
        token = (data or {}).get("access_token")
        if not token:
            raise MyGarageAuthError("Login response missing access_token")
        self._jwt = token
        return token

    async def _ensure_jwt(self) -> str:
        if not self._jwt:
            await self.async_login()
        assert self._jwt is not None
        return self._jwt

    async def _jwt_headers(self) -> dict[str, str]:
        token = await self._ensure_jwt()
        return {"Authorization": f"Bearer {token}"}

    async def async_get_livelink_status(self, vin: str) -> dict[str, Any]:
        headers = await self._jwt_headers()
        return await self._request(
            "GET",
            f"/api/vehicles/{vin.upper()}/livelink/status",
            headers=headers,
            retry_auth=True,
        )

    async def async_list_dtcs(self, vin: str) -> dict[str, Any]:
        headers = await self._jwt_headers()
        return await self._request(
            "GET",
            f"/api/vehicles/{vin.upper()}/livelink/dtcs",
            headers=headers,
            params={"include_cleared": "false"},
            retry_auth=True,
        )

    async def async_list_reminders(
        self, vin: str, *, status: str = "pending"
    ) -> list[dict[str, Any]]:
        headers = await self._jwt_headers()
        data = await self._request(
            "GET",
            f"/api/vehicles/{vin.upper()}/reminders",
            headers=headers,
            params={"status": status},
            retry_auth=True,
        )
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.get("reminders") or data.get("items") or [])
        return []
