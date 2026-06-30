#!/usr/bin/env python3

from api_client import print_json, request_api


def get_move_status(move_id: int) -> dict | None:
    """GET /chassis/moves/{id}."""
    data = request_api("GET", f"/chassis/moves/{int(move_id)}")
    return data if isinstance(data, dict) else None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2 or not sys.argv[1].strip().lstrip("-").isdigit():
        mid = input("Move id: ").strip()
        if not mid.isdigit():
            sys.exit(1)
    else:
        mid = sys.argv[1]
    mv = get_move_status(int(mid))
    if mv is not None:
        print_json(mv)
