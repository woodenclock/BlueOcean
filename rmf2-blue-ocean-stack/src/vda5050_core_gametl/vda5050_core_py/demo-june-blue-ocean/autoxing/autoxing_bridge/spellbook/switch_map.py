#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from api_client import parse_json_file, print_json, request_api


def switch_map_payload(payload: dict[str, Any]) -> dict | None:
    """POST /chassis/current-map with a JSON body (any OpenAPI variant)."""
    data = request_api("POST", "/chassis/current-map", json_body=payload)
    return data if isinstance(data, dict) else None


def switch_map_by_numeric_id(map_id: int) -> dict | None:
    return switch_map_payload({"map_id": int(map_id)})


def switch_map_by_uid(map_uid: str) -> dict | None:
    return switch_map_payload({"map_uid": str(map_uid)})


def switch_map_by_file_uri(*, data_url: str, map_name: str) -> dict | None:
    return switch_map_payload({"data_url": data_url, "map_name": map_name})


if __name__ == "__main__":
    from get_maps import get_maps

    parser = argparse.ArgumentParser(
        description="POST /chassis/current-map — activate map (id, uid, file URI, or raw JSON).",
    )
    parser.add_argument(
        "map_id_positional",
        nargs="?",
        type=int,
        help="numeric map_id (legacy)",
    )
    parser.add_argument("--uid", "--map-uid", dest="map_uid", help="activate by map_uid string")
    parser.add_argument("--data-url", help="file:// URI on robot (v2.11.0+); use with --map-name")
    parser.add_argument("--map-name", help="map name for SetCurrentMapByFile")
    parser.add_argument("--body-file", help="JSON file for full request body (any variant)")
    parser.add_argument("--body", help="JSON string for full request body")
    args = parser.parse_args()

    out: dict | None = None

    if args.body_file:
        out = switch_map_payload(parse_json_file(args.body_file))
    elif args.body:
        out = switch_map_payload(json.loads(args.body))
    elif args.map_uid:
        out = switch_map_by_uid(args.map_uid)
    elif args.data_url or args.map_name:
        if not (args.data_url and args.map_name):
            print("Both --data-url and --map-name are required for file-based activation.", file=sys.stderr)
            sys.exit(1)
        out = switch_map_by_file_uri(data_url=args.data_url, map_name=args.map_name)
    elif args.map_id_positional is not None:
        out = switch_map_by_numeric_id(args.map_id_positional)
    else:
        from cli_tables import print_maps_table
        from get_maps import get_maps

        maps = get_maps() or []
        if not maps:
            print("No maps.")
            sys.exit(1)
        print_maps_table(maps)
        u = input("Select map index (or enter numeric map id): ").strip()
        sel: int | None = None
        if u.isdigit() and int(u) < len(maps):
            mid = maps[int(u)].get("id")
            if mid is not None:
                sel = int(mid)
        elif u.isdigit():
            sel = int(u)
        if sel is None:
            print("No map selected.")
            sys.exit(1)
        out = switch_map_by_numeric_id(sel)

    if out is not None:
        print_json(out)
