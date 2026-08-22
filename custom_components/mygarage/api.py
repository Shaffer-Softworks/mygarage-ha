"""Async HTTP client for the MyGarage API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

_LOGGER = logging.getLogger(__name__)


class MyGarageApiError(Exception):
    """Raised when the MyGarage API returns an error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MyGarageAuthError(MyGarageApiError):
    """Raised for authentication failures."""


class MyGarageApiClient:
    """httpx client covering widget, webhook, and JWT REST surfaces."""

    def __init__(
        self,
        base_url: str,
        *,
        widget_api_key: str = "",
        webhook_token: str = "",
        username: str = "",
        password: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._widget_api_key = widget_api_key.strip()
        self._webhook_token = webhook_token.strip()
        self._username = username.strip()
        self._password = password
        self._jwt: str | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def has_webhook(self) -> bool:
        return bool(self._webhook_token)

    @property
    def has_jwt_credentials(self) -> bool:
        return bool(self._username and self._password)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(20.0, connect=10.0),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_auth: bool = False,
    ) -> Any:
        client = await self._get_client()
        try:
            response = await client.request(
                method,
                path,
                headers=headers,
                json=json,
                params=params,
            )
        except httpx.HTTPError as err:
            raise MyGarageApiError(str(err)) from err

        if response.status_code == 401 and retry_auth and self.has_jwt_credentials:
            await self.async_login()
            headers = dict(headers or {})
            headers["Authorization"] = f"Bearer {self._jwt}"
            return await self._request(
                method,
                path,
                headers=headers,
                json=json,
                params=params,
                retry_auth=False,
            )

        if response.status_code in (401, 403):
            raise MyGarageAuthError(
                f"Unauthorized: {response.text}", status_code=response.status_code
            )
        if response.status_code >= 400:
            raise MyGarageApiError(
                f"{response.status_code}: {response.text}",
                status_code=response.status_code,
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

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
            json=payload,
        )

    async def async_webhook_odometer(self, payload: dict[str, Any]) -> Any:
        return await self._request(
            "POST",
            "/api/v1/webhooks/odometer",
            headers=self._webhook_headers(),
            json=payload,
        )

    async def async_webhook_complete_reminder(
        self, vin: str, reminder_id: int
    ) -> Any:
        return await self._request(
            "POST",
            "/api/v1/webhooks/reminders/complete",
            headers=self._webhook_headers(),
            json={"vin": vin, "reminder_id": reminder_id},
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
            json={"username": self._username, "password": self._password},
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
