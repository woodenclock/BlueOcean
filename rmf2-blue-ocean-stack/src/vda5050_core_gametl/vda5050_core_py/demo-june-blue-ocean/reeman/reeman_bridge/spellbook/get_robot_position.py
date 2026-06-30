#!/usr/bin/env python3
"""Alias for ``get_pose`` — Reeman REST ``GET /reeman/pose``."""

import sys

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT

from get_pose import get_pose


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_robot_position(timeout: float | None = None) -> dict | None:
    """Get Reeman robot position via REST API."""
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


def get_robot_position(timeout: float | None = None) -> dict | None:
    """Get robot position (Reeman FlyBoat REST only)."""
    return get_pose(timeout=timeout)


if __name__ == "__main__":
    pose = get_robot_position()
    if pose is not None:
        print_json(pose)
    else:
        sys.exit(1)
