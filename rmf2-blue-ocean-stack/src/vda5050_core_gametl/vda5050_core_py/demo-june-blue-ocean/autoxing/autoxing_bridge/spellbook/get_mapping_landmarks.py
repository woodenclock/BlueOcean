#!/usr/bin/env python3
"""GET /mappings/{id}/landmarks.json — landmarks from a completed mapping (v2.11.0+)."""

import sys

from api_client import print_json, request_api


def get_mapping_landmarks(mapping_id: int) -> list | None:
    data = request_api("GET", f"/mappings/{int(mapping_id)}/landmarks.json")
    return data if isinstance(data, list) else data


if __name__ == "__main__":
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not arg.isdigit():
        print("Usage: get_mapping_landmarks <mapping_id>")
        raise SystemExit(1)
    result = get_mapping_landmarks(int(arg))
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
