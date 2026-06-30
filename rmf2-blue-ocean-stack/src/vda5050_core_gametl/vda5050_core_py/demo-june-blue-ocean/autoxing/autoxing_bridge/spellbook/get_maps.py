#!/usr/bin/env python3

from api_client import print_json, request_api


def get_maps() -> list | None:
    """GET /maps/ — all maps on robot."""
    data = request_api("GET", "/maps/")
    return data if isinstance(data, list) else None


if __name__ == "__main__":
    maps = get_maps()
    if maps is not None:
        print_json(maps)
