#!/usr/bin/env python3
"""Minimal MyGarage API mock for README screenshot capture."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8686
WIDGET_KEY = "mgwk_screenshot_dev_key_000000000000"
WEBHOOK_TOKEN = "webhook_screenshot_dev_token"
JWT_USER = "ha"
JWT_PASS = "ha"

SUMMARY = {
    "total_vehicles": 2,
    "active_vehicles": 2,
    "archived_vehicles": 0,
    "total_overdue_maintenance": 1,
    "total_upcoming_maintenance": 2,
    "total_service_records": 18,
    "total_fuel_records": 42,
    "total_documents": 6,
    "total_notes": 3,
    "total_photos": 12,
}

VEHICLES = [
    {"vin": "1HGCM82633A004352", "label": "2018 Subaru Outback"},
    {"vin": "5YJSA1E26HF000001", "label": "2017 Tesla Model S"},
]

VEHICLE_DETAIL = {
    "1HGCM82633A004352": {
        "label": "2018 Subaru Outback",
        "year": 2018,
        "make": "Subaru",
        "model": "Outback",
        "odometer": 87432,
        "odometer_km": 140708,
        "odometer_date": "2026-08-20",
        "recent_mpg": 27.4,
        "average_mpg": 26.8,
        "recent_l_per_100km": 8.6,
        "average_l_per_100km": 8.8,
        "latest_hours": None,
        "upcoming_maintenance": 1,
        "overdue_maintenance": 1,
        "service_records": 11,
        "fuel_records": 28,
        "last_service_date": "2026-06-12",
        "last_fuel_date": "2026-08-18",
        "documents": 4,
        "notes": 2,
        "photos": 8,
    },
    "5YJSA1E26HF000001": {
        "label": "2017 Tesla Model S",
        "year": 2017,
        "make": "Tesla",
        "model": "Model S",
        "odometer": 52100,
        "odometer_km": 83847,
        "odometer_date": "2026-08-19",
        "recent_mpg": None,
        "average_mpg": None,
        "recent_l_per_100km": None,
        "average_l_per_100km": None,
        "latest_hours": None,
        "upcoming_maintenance": 1,
        "overdue_maintenance": 0,
        "service_records": 7,
        "fuel_records": 14,
        "last_service_date": "2026-05-03",
        "last_fuel_date": "2026-08-17",
        "documents": 2,
        "notes": 1,
        "photos": 4,
    },
}

LIVELINK = {
    "vin": "1HGCM82633A004352",
    "device_id": "wican-demo",
    "device_status": "online",
    "ecu_status": "online",
    "last_seen": "2026-08-22T18:30:00Z",
    "battery_voltage": 12.6,
    "rssi": -58,
    "current_session_id": 42,
    "session_started_at": "2026-08-22T18:25:00Z",
    "session_duration_seconds": 300,
    "latest_values": [
        {
            "param_key": "speed",
            "value": 42.0,
            "unit": "km/h",
            "display_name": "Speed",
            "timestamp": "2026-08-22T18:30:00Z",
            "in_warning": False,
        },
        {
            "param_key": "rpm",
            "value": 1850.0,
            "unit": "rpm",
            "display_name": "Engine RPM",
            "timestamp": "2026-08-22T18:30:00Z",
            "in_warning": False,
        },
    ],
}

DTCS = {
    "dtcs": [
        {
            "id": 1,
            "code": "P0420",
            "description": "Catalyst system efficiency below threshold",
            "severity": "warning",
            "vin": "1HGCM82633A004352",
            "device_id": "wican-demo",
            "is_active": True,
        }
    ],
    "total": 1,
    "active_count": 1,
    "critical_count": 0,
}

REMINDERS = [
    {
        "id": 7,
        "vin": "1HGCM82633A004352",
        "title": "Oil change",
        "reminder_type": "service",
        "due_date": "2026-09-01",
        "due_mileage_km": 142000,
        "status": "pending",
    }
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: ARG002
        return

    def _send(self, code: int, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/health", "/api/health"):
            return self._send(200, {"status": "healthy", "app": "MyGarage", "version": "screenshot-mock"})
        if path == "/api/v2/widget/summary":
            if self.headers.get("X-API-Key") != WIDGET_KEY:
                return self._send(401, {"detail": "Invalid API key"})
            return self._send(200, SUMMARY)
        if path == "/api/v2/widget/vehicles":
            if self.headers.get("X-API-Key") != WIDGET_KEY:
                return self._send(401, {"detail": "Invalid API key"})
            return self._send(200, {"vehicles": VEHICLES})
        if path.startswith("/api/v2/widget/vehicle/"):
            if self.headers.get("X-API-Key") != WIDGET_KEY:
                return self._send(401, {"detail": "Invalid API key"})
            vin = path.rsplit("/", 1)[-1].upper()
            detail = VEHICLE_DETAIL.get(vin)
            if not detail:
                return self._send(404, {"detail": "Not found"})
            return self._send(200, detail)
        if path.endswith("/livelink/status"):
            return self._send(200, LIVELINK)
        if path.endswith("/livelink/dtcs"):
            return self._send(200, DTCS)
        if path.endswith("/reminders"):
            return self._send(200, REMINDERS)
        self._send(404, {"detail": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/auth/login":
            data = self._read_json()
            if data.get("username") == JWT_USER and data.get("password") == JWT_PASS:
                return self._send(
                    200,
                    {
                        "access_token": "screenshot-mock-jwt",
                        "token_type": "bearer",
                        "expires_in": 3600,
                    },
                )
            return self._send(401, {"detail": "Invalid credentials"})
        if path.startswith("/api/v1/webhooks/"):
            if self.headers.get("X-Webhook-Token") != WEBHOOK_TOKEN:
                return self._send(401, {"detail": "Invalid webhook token"})
            return self._send(200, {"ok": True})
        self._send(404, {"detail": "Not found"})


def main() -> None:
    server = HTTPServer((HOST, PORT), Handler)
    print(f"MyGarage screenshot mock listening on http://{HOST}:{PORT}")
    print(f"Widget key: {WIDGET_KEY}")
    print(f"JWT: {JWT_USER}/{JWT_PASS}")
    server.serve_forever()


if __name__ == "__main__":
    main()
