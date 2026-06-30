#!/usr/bin/env python3

from api_client import print_json, request_api


def get_current_map() -> dict | None:
    """GET /chassis/current-map — active map summary."""
    data = request_api("GET", "/chassis/current-map")
    return data if isinstance(data, dict) else None


def current_map_id(m: dict | None = None) -> int | None:
    """Return numeric map id from payload, or None if not in library (id == -1 etc.)."""
    if m is None:
        m = get_current_map()
        if m is None:
            return None
    mid = m.get("id")
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
