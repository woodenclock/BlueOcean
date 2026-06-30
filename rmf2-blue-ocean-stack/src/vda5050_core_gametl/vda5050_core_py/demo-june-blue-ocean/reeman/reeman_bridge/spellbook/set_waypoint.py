#!/usr/bin/env python3

import argparse
import sys
from typing import Optional

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT


# UI labels -> API type values.
# Known from the Reeman manual:
# - normal / waypoint
# - delivery
# - production
# - charge / charging_pile
#
# The rest are kept as distinct values because they appear in the web UI.
VALID_TYPES = {
    "waypoint": "normal",
    "normal": "normal",
    "delivery": "delivery",
    "avoidance": "avoid",
    "production": "production",
    "recycling": "recycle",
    "qr_code": "qr_code",
    "elevator_entrance": "elevator_entrance",
    "inside_elevator": "inside_elevator",
    "elevator_exit": "elevator_exit",
    "charging_pile": "charge",
    "charge": "charge",
    "charging": "charge",
}

PROMPT_TYPES = [
    "waypoint",
    "delivery",
    "avoidance",
    "production",
    "recycling",
    "qr_code",
    "elevator_entrance",
    "inside_elevator",
    "elevator_exit",
    "charging_pile",
]

API_TYPES = sorted(set(VALID_TYPES.keys()))


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_pose(timeout: float | None = None) -> dict | None:
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/pose",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Reeman REST error while getting pose: {e}", file=sys.stderr)
        return None


def _prompt_name() -> str:
    while True:
        name = input("Name? ").strip()
        if name:
            return name
        print("Name cannot be empty.", file=sys.stderr)


def _prompt_waypoint_type() -> str:
    print("Waypoint Type?")
    for i, t in enumerate(PROMPT_TYPES, start=1):
        print(f"{i}. {t}")

    while True:
        choice = input("Select [1-10]: ").strip()

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(PROMPT_TYPES):
                return PROMPT_TYPES[idx - 1]

        choice_lower = choice.lower()
        if choice_lower in VALID_TYPES:
            return choice_lower

        print("Invalid selection. Choose 1-10 or type one of the names above.", file=sys.stderr)


def set_reeman_waypoint(
    name: str,
    waypoint_type: str = "normal",
    timeout: float | None = None,
) -> dict | None:
    """
    Set a Reeman waypoint using current robot position and orientation.

    Reeman API:
      POST /cmd/position
      body:
      {
        "name": "Point_A",
        "type": "normal",
        "pose": {"x": ..., "y": ..., "theta": ...}
      }
    """
    waypoint_type = VALID_TYPES.get(waypoint_type, waypoint_type)

    pose = get_reeman_pose(timeout=timeout)
    if pose is None:
        return None

    payload = {
        "name": name,
        "type": waypoint_type,
        "pose": {
            "x": pose.get("x"),
            "y": pose.get("y"),
            "theta": pose.get("theta"),
        },
    }

    try:
        resp = requests.post(
            f"{_robot_base_url()}/cmd/position",
            json=payload,
            timeout=timeout or 5,
        )
        resp.raise_for_status()

        try:
            result = resp.json()
        except Exception:
            result = {}

        return {
            "status": "success",
            "name": name,
            "type": waypoint_type,
            "pose": payload["pose"],
            "response": result,
        }

    except Exception as e:
        print(f"Reeman REST error while setting waypoint: {e}", file=sys.stderr)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set Reeman waypoint using current robot pose."
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="Waypoint name, e.g. Point_A",
    )
    parser.add_argument(
        "--type",
        default=None,
        choices=API_TYPES,
        help="Waypoint type. If omitted, you will be asked interactively.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10,
        help="REST timeout in seconds. Default: 10",
    )

    args = parser.parse_args()

    name = args.name or _prompt_name()
    waypoint_type = args.type or _prompt_waypoint_type()

    result = set_reeman_waypoint(
        name=name,
        waypoint_type=waypoint_type,
        timeout=args.timeout,
    )

    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    main()