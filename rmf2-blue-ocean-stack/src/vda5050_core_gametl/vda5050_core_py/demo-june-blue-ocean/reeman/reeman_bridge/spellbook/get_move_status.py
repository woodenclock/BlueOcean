#!/usr/bin/env python3

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def _normalize_reeman_move_status(data: dict, move_id: int | None = None) -> dict:
    res = data.get("res")
    reason = data.get("reason")

    if res == 1:
        state = "moving"
        status = "running"
    elif res == 3 and reason == 0:
        state = "idle"
        status = "succeeded"
    elif res == 3 and reason != 0:
        state = "idle"
        status = "failed"
    elif res == 4:
        state = "idle"
        status = "cancelled"
    elif res == 6:
        state = "idle"
        status = "ready"
    else:
        state = "unknown"
        status = "unknown"

    return {
        "id": move_id,
        "state": state,
        "status": status,
        "res": res,
        "reason": reason,
        "goal": data.get("goal"),
        "dist": data.get("dist"),
        "mileage": data.get("mileage"),
        "raw": data,
    }


def get_reeman_move_status(
    move_id: int | None = None,
    timeout: float | None = None,
) -> dict | None:
    """Get Reeman move/navigation status via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/nav_status",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, dict):
            return None

        return _normalize_reeman_move_status(data, move_id=move_id)

    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None
    

def get_move_status(move_id: int, timeout: float | None = None) -> dict | None:
    # """GET /chassis/moves/{id}."""
    """
    Get move status via Reeman REST ``GET /reeman/nav_status``.
    """
    return get_reeman_move_status(move_id=move_id, timeout=timeout)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2 or not sys.argv[1].strip().lstrip("-").isdigit():
        mid = input("Move id: ").strip()
        if not mid.isdigit():
            sys.exit(1)
    else:
        mid = sys.argv[1]
    mv = get_move_status(int(mid))
    if mv is not None:
        print_json(mv)
