#!/usr/bin/env python3
"""Get battery state via Reeman REST ``GET /reeman/base_encode``."""

import sys

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_battery_state(timeout: float | None = None) -> dict | None:
    """Get Reeman battery state via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/base_encode",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "percentage": data.get("battery"),
            "battery": data.get("battery"),
            "charge_flag": data.get("chargeFlag"),
            "emergency_button": data.get("emergencyButton"),
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_battery_state(timeout: float | None = None) -> dict | None:
    """Get battery state (Reeman FlyBoat REST only)."""
    return get_reeman_battery_state(timeout=timeout)


if __name__ == "__main__":
    state = get_battery_state()
    if state is not None:
        print_json(state)
    else:
        sys.exit(1)
