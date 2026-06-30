#!/usr/bin/env python3
"""Check robot movement via Reeman REST ``GET /reeman/nav_status``."""

from __future__ import annotations

import requests

from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_robot_movement(timeout: float | None = None) -> str | None:
    """Get Reeman robot movement state via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/nav_status",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()

        res = data.get("res")
        reason = data.get("reason")

        if res == 1:
            return "MOVING"

        if res == 3:
            if reason == 0:
                return "IDLE_TERMINAL_RECENT"
            if reason == 1:
                return "IDLE_FAILED_RECENT"
            return "IDLE_TERMINAL_RECENT"

        if res == 4:
            return "IDLE_CANCELLED_RECENT"

        if res == 6:
            if reason == 2:
                return "IDLE_EMERGENCY_STOP"
            if reason == 6:
                return "IDLE_LOCALIZATION_ABNORMAL"
            return "IDLE"

        return f"UNKNOWN_REEMAN_RES_{res}"

    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def check_robot_movement(*, duration_sec: float = 15.0) -> str:
    """Check robot movement state (Reeman FlyBoat REST only)."""
    reeman_state = get_reeman_robot_movement(timeout=duration_sec)
    if reeman_state is not None:
        return reeman_state
    return "NO_DATA"


if __name__ == "__main__":
    print("Reading /reeman/nav_status …")
    label = check_robot_movement()
    print(label)
