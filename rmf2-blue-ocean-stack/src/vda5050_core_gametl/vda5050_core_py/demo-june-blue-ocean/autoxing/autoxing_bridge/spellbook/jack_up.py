#!/usr/bin/env python3
"""Raise jack device — POST /services/jack_up (monitor progress via ``jack_state``)."""

from api_client import print_json, request_api


def jack_up() -> dict | None:
    """POST /services/jack_up — raise jack; monitor via WebSocket ``/jack_state``."""
    data = request_api("POST", "/services/jack_up", json_body={})
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    out = jack_up()
    if out is not None:
        print_json(out)
