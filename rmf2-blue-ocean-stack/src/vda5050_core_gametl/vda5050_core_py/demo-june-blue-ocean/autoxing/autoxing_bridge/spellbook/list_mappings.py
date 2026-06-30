#!/usr/bin/env python3
"""GET /mappings/ — list mapping tasks."""

from api_client import print_json, request_api


def list_mappings() -> list | None:
    data = request_api("GET", "/mappings/")
    return data if isinstance(data, list) else None


if __name__ == "__main__":
    result = list_mappings()
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
