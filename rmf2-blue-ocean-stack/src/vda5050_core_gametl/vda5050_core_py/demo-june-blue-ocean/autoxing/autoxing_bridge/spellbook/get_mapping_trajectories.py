#!/usr/bin/env python3
"""GET /mappings/{id}/trajectories.json — mapping trajectory polylines."""

import sys

from api_client import print_json, request_api


def get_mapping_trajectories(mapping_id: int) -> list | None:
    data = request_api("GET", f"/mappings/{int(mapping_id)}/trajectories.json")
    return data if isinstance(data, list) else data


if __name__ == "__main__":
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not arg.isdigit():
        print("Usage: get_mapping_trajectories <mapping_id>")
        raise SystemExit(1)
    result = get_mapping_trajectories(int(arg))
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
