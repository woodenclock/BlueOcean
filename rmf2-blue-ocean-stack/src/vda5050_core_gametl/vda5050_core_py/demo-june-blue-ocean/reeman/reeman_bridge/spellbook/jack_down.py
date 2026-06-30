#!/usr/bin/env python3

#"""Lower jack device — POST /services/jack_down (monitor progress via ``jack_state``)."""
"""
Lower jack device.

Reeman FlyBoat uses REST API:
POST /cmd/hydraulic_down

Existing OpenAPI REST path is kept as fallback:
POST /services/jack_down
"""

import requests

from api_client import print_json, request_api
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def reeman_jack_down(timeout: float | None = None) -> dict | None:
    """Lower Reeman hydraulic jack via REST API."""
    try:
        resp = requests.post(
            f"{_robot_base_url()}/cmd/hydraulic_down",
            json={},
            timeout=timeout or 5,
        )
        resp.raise_for_status()

        try:
            data = resp.json()
        except ValueError:
            data = {}

        return {
            "status": "success",
            "command": "hydraulic_down",
            "raw": data,
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def jack_down(timeout: float | None = None) -> dict | None:
    """
    Lower jack device.

    Reeman FlyBoat uses REST API.
    Existing OpenAPI REST path is kept as fallback.
    """
    
    state = reeman_jack_down(timeout=timeout)
    if state is not None:
        return state

    try:
        data = request_api("POST", "/services/jack_down", json_body={})
        return data if isinstance(data, dict) else data
    except Exception as e:
        print(f"OpenAPI fallback error: {e}")
        return None
    
    # data = request_api("POST", "/services/jack_down", json_body={})
    # return data if isinstance(data, dict) else data


if __name__ == "__main__":
    out = jack_down()
    if out is not None:
        print_json(out)
