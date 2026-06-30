#!/usr/bin/env python3
"""Read robot pose via Reeman REST ``GET /reeman/pose``."""

import sys

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_pose(timeout: float | None = None) -> dict | None:
    """Get Reeman pose via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/pose",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "x": data.get("x"),
            "y": data.get("y"),
            "theta": data.get("theta"),
            "pos": [data.get("x"), data.get("y")],
            "ori": data.get("theta"),
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_pose(timeout: float | None = None) -> dict | None:
    """Get robot pose (Reeman FlyBoat REST only)."""
    return get_reeman_pose(timeout=timeout)


if __name__ == "__main__":
    pose = get_pose()
    if pose is not None:
        print_json(pose)
    else:
        sys.exit(1)
