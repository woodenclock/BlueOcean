#!/usr/bin/env python3
"""PATCH /maps/{id} — update map name or overlays."""

from __future__ import annotations

import argparse
import json
import sys

from api_client import parse_json_file, print_json, request_api


def patch_map(map_id: int, body: dict) -> dict | None:
    data = request_api("PATCH", f"/maps/{int(map_id)}", json_body=body, timeout=60)
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="PATCH /maps/{id}")
    p.add_argument("map_id", type=int, nargs="?", help="numeric map id")
    p.add_argument("--body-file", help="JSON patch body (map_name, overlays, …)")
    p.add_argument("--body", help="JSON patch body string")
    p.add_argument("--map-name", help="shortcut: set map_name only")
    p.add_argument("--overlays-file", help="shortcut: read GeoJSON overlays string from file")
    args = p.parse_args()

    map_id = args.map_id
    if map_id is None:
        from get_maps import get_maps

        from cli_tables import print_maps_table
        from get_maps import get_maps

        maps = get_maps() or []
        if not maps:
            print("No maps.")
            raise SystemExit(1)
        print_maps_table(maps)
        u = input("Select map index or enter numeric id: ").strip()
        if u.isdigit() and int(u) < len(maps):
            map_id = int(maps[int(u)].get("id"))
        elif u.isdigit():
            map_id = int(u)
        else:
            raise SystemExit(1)

    if args.body_file:
        body = parse_json_file(args.body_file)
    elif args.body:
        body = json.loads(args.body)
    elif args.map_name or args.overlays_file:
        body = {}
        if args.map_name:
            body["map_name"] = args.map_name
        if args.overlays_file:
            body["overlays"] = (
                open(args.overlays_file, encoding="utf-8").read().strip()
            )
    else:
        p.error("need --body-file, --body, --map-name, or --overlays-file")

    if not isinstance(body, dict):
        print("JSON body must be an object.", file=sys.stderr)
        raise SystemExit(1)

    result = patch_map(map_id, body)
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
