#!/usr/bin/env python3
"""Bootstrap HA config entry for MyGarage screenshot capture."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

HA_URL = os.environ.get("HA_URL", "http://localhost:8123").rstrip("/")
MOCK_URL = os.environ.get("MYGARAGE_MOCK_URL", "http://host.docker.internal:8686")
WIDGET_KEY = "mgwk_screenshot_dev_key_000000000000"
WEBHOOK_TOKEN = "webhook_screenshot_dev_token"
JWT_USER = "ha"
JWT_PASS = "ha"
DOMAIN = "mygarage"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _token() -> str:
    refresh = os.environ.get("HA_REFRESH_TOKEN", "").strip()
    if not refresh:
        raise RuntimeError("Set HA_REFRESH_TOKEN")
    resp = requests.post(
        f"{HA_URL}/auth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": f"{HA_URL}/",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def wait_for_ha(timeout: int = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{HA_URL}/", timeout=5).status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    raise TimeoutError(f"HA not ready at {HA_URL}")


def restart_ha() -> None:
    subprocess.run(
        ["docker", "compose", "restart", "homeassistant"],
        cwd=REPO_ROOT,
        check=True,
    )
    wait_for_ha(240)


def list_entries(token: str) -> list[dict]:
    resp = requests.get(
        f"{HA_URL}/api/config/config_entries/entry",
        headers=_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return [e for e in resp.json() if e.get("domain") == DOMAIN]


def delete_entry(token: str, entry_id: str) -> None:
    resp = requests.delete(
        f"{HA_URL}/api/config/config_entries/entry/{entry_id}",
        headers=_headers(token),
        timeout=60,
    )
    resp.raise_for_status()


def create_entry_via_flow(token: str) -> str:
    resp = requests.post(
        f"{HA_URL}/api/config/config_entries/flow",
        headers=_headers(token),
        json={"handler": DOMAIN, "show_advanced_options": True},
        timeout=30,
    )
    resp.raise_for_status()
    flow = resp.json()
    flow_id = flow["flow_id"]

    resp = requests.post(
        f"{HA_URL}/api/config/config_entries/flow/{flow_id}",
        headers=_headers(token),
        json={
            "url": MOCK_URL,
            "widget_api_key": WIDGET_KEY,
            "webhook_token": WEBHOOK_TOKEN,
            "username": JWT_USER,
            "password": JWT_PASS,
        },
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("type") != "create_entry":
        raise RuntimeError(f"Unexpected flow result: {result}")
    return result["result"]["entry_id"]


def wait_for_entities(token: str, min_entities: int = 5, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{HA_URL}/api/states",
            headers=_headers(token),
            timeout=30,
        )
        resp.raise_for_status()
        count = sum(1 for s in resp.json() if s["entity_id"].startswith(f"{DOMAIN}."))
        if count >= min_entities:
            print(f"Found {count} {DOMAIN} entities")
            return
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for {DOMAIN} entities")


def wait_for_devices(timeout: int = 120) -> int:
    path = REPO_ROOT / "docker_data" / "config" / ".storage" / "core.device_registry"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            devices = (data.get("data") or {}).get("devices") or []
            matched = [
                d
                for d in devices
                if any(
                    len(ident) >= 2 and ident[0] == DOMAIN
                    for ident in (d.get("identifiers") or [])
                )
            ]
            if len(matched) >= 2:
                print(f"Found {len(matched)} {DOMAIN} devices")
                return len(matched)
        time.sleep(5)
    return 0


def main() -> int:
    wait_for_ha()
    token = _token()

    for entry in list_entries(token):
        print(f"Removing existing entry {entry['entry_id']}")
        delete_entry(token, entry["entry_id"])

    entry_id = create_entry_via_flow(token)
    print(f"Created config entry {entry_id}")

    wait_for_entities(token)
    device_count = wait_for_devices()
    if device_count < 2:
        print("Devices not registered yet; restarting HA", file=sys.stderr)
        restart_ha()
        token = _token()
        wait_for_entities(token)
        device_count = wait_for_devices()
        if device_count < 2:
            raise RuntimeError("MyGarage devices were not created after restart")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
