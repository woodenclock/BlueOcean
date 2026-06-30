#!/usr/bin/env python3

import requests

from api_client import print_json, request_api
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_maps(timeout: float | None = None) -> list | dict | None:
    """Get Reeman map list via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/history_map",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_maps(timeout: float | None = None) -> list | dict | None:
    # """GET /maps/ — all maps on robot."""
    """
    Get all maps on robot.
    Reeman FlyBoat uses REST API.
    Existing OpenAPI path is kept as fallback.
    """
    maps = get_reeman_maps(timeout=timeout)
    if maps is not None:
        return maps
    try:
        data = request_api("GET", "/maps/")
        return data if isinstance(data, list) else None
    except Exception as e:
        print(f"OpenAPI fallback error: {e}")
        return None
    

if __name__ == "__main__":
    maps = get_maps()
    if maps is not None:
        print_json(maps)
