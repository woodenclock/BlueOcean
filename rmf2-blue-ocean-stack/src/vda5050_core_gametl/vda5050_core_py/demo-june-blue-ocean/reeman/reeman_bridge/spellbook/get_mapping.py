#!/usr/bin/env python3
"""GET /mappings/{id} — mapping task detail."""

import sys

from api_client import print_json, request_api


def get_mapping(mapping_id: int) -> dict | None:
    data = request_api("GET", f"/mappings/{int(mapping_id)}")
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not arg.isdigit():
        print("Usage: get_mapping <mapping_id>")
        raise SystemExit(1)
    result = get_mapping(int(arg))
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
