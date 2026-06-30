#!/usr/bin/env python3

import requests

from api_client import print_json, request_api
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_current_map(timeout: float | None = None) -> dict | None:
    """Get Reeman current map via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/current_map",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, dict):
            return None

        return {
            "alias": data.get("alias"),
            "name": data.get("name"),
            "map_id": data.get("name"),
            "raw": data,
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None
    

def get_current_map(timeout: float | None = None) -> dict | None:
    # """GET /chassis/current-map — active map summary."""
    """
    Get active map summary.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI path is kept as fallback.
    """
    state = get_reeman_current_map(timeout=timeout)
    if state is not None:
        return state

    try:
        data = request_api("GET", "/chassis/current-map")
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"OpenAPI error: {e}")
        return None

def current_map_id(m: dict | None = None) -> int | None:
    """Return numeric map id from payload, or None if not in library (id == -1 etc.)."""
    if m is None:
        m = get_current_map()
        if m is None:
            return None
    mid = m.get("id") or m.get("map_id") or m.get("name")
    try:
        i = int(mid)
    except (TypeError, ValueError):
        return None
    if i < 0:
        return None
    return i


if __name__ == "__main__":
    cm = get_current_map()
    if cm is not None:
        print_json(cm)
