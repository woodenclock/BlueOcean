#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests

from api_client import parse_json_file, print_json, request_api
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    if str(ip).startswith(("http://", "https://")):
        return str(ip).rstrip("/")
    return f"{prefix}{ip}".rstrip("/")


def switch_reeman_map(map_name: str, timeout: float | None = None) -> dict | None:
    """
    Switch Reeman FlyBoat map via REST API.

    Reeman endpoint:
        POST /cmd/apply_map
        body: {"name": "<map name>"}
    """
    try:
        resp = requests.post(
            f"{_robot_base_url()}/cmd/apply_map",
            json={"name": str(map_name)},
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json() if resp.content else {}

        return {
            "status": "success",
            "map_name": map_name,
            "raw": data,
        }
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def normalize_map_item(m: Any) -> dict[str, Any]:
    if not isinstance(m, dict):
        return {"name": str(m)}

    name = (
        m.get("name")
        or m.get("alias")
        or m.get("map_name")
        or m.get("mapName")
        or m.get("map")
        or m.get("id")
        or m.get("uid")
        or m.get("map_uid")
    )

    return {
        "id": m.get("id") or m.get("map_id") or "",
        "map_uid": m.get("map_uid") or m.get("uid") or m.get("name") or "",
        "name": name or json.dumps(m, ensure_ascii=False),
        "raw": m,
    }


def normalize_maps(maps: Any) -> list[dict[str, Any]]:
    if isinstance(maps, list):
        return [normalize_map_item(m) for m in maps]

    if isinstance(maps, dict):
        for key in ("maps", "data", "map_list", "history_map", "waypoints"):
            if isinstance(maps.get(key), list):
                return normalize_maps(maps[key])

        return [
            normalize_map_item(v if isinstance(v, dict) else {"name": v or k})
            for k, v in maps.items()
        ]

    return []


def switch_map_payload(payload: dict[str, Any]) -> dict | None:
    # """POST /chassis/current-map with a JSON body (any OpenAPI variant)."""
    """
    Switch map.

    Reeman FlyBoat uses REST API.
    Existing OpenAPI path is kept as fallback.
    """
    reeman_map_name = (
        payload.get("name")
        or payload.get("map_name")
        or payload.get("map_uid")
    )

    if reeman_map_name:
        data = switch_reeman_map(str(reeman_map_name))
        if data is not None:
            return data
        
    data = request_api("POST", "/chassis/current-map", json_body=payload)
    return data if isinstance(data, dict) else None


def switch_map_by_numeric_id(map_id: int) -> dict | None:
    return switch_map_payload({"map_id": int(map_id)})


def switch_map_by_uid(map_uid: str) -> dict | None:
    return switch_map_payload({"map_uid": str(map_uid)})


def switch_map_by_file_uri(*, data_url: str, map_name: str) -> dict | None:
    return switch_map_payload({"data_url": data_url, "map_name": map_name})


def switch_map_by_name(map_name: str) -> dict | None:
    return switch_map_payload({"name": str(map_name)})


if __name__ == "__main__":
    from get_maps import get_maps

    parser = argparse.ArgumentParser(
        #description="POST /chassis/current-map — activate map (id, uid, file URI, or raw JSON).",)
        description="Activate map. Supports Reeman REST API with OpenAPI fallback.",
    )
    parser.add_argument(
        "map_id_positional",
        nargs="?",
        type=int,
        help="numeric map_id (legacy)",
    )
    parser.add_argument("--uid", "--map-uid", dest="map_uid", help="activate by map_uid string")
    parser.add_argument("--name", "--reeman-name", dest="reeman_name", help="activate Reeman map by name")
    parser.add_argument("--data-url", help="file:// URI on robot; use with --map-name")
    parser.add_argument("--map-name", help="map name for file-based activation")
    parser.add_argument("--body-file", help="JSON file for full request body")
    parser.add_argument("--body", help="JSON string for full request body")
    args = parser.parse_args()

    out: dict | None = None

    if args.body_file:
        out = switch_map_payload(parse_json_file(args.body_file))
    
    elif args.body:
        out = switch_map_payload(json.loads(args.body))

    elif args.reeman_name:
        out = switch_map_by_name(args.reeman_name)
    
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

        maps = normalize_maps(get_maps())
        if not maps:
            print("No maps.")
            sys.exit(1)
        print_maps_table(maps)
        u = input("Select map index, numeric map id, or Reeman map name: ").strip()

        selected_map: dict[str, Any] | None = None

        if u.isdigit() and int(u) < len(maps):
            selected_map = maps[int(u)]

        if selected_map:
            reeman_name = (
                selected_map.get("name")
                or selected_map.get("alias")
                or selected_map.get("map_name")
                or selected_map.get("map_uid")
            )

            if reeman_name:
                out = switch_map_by_name(str(reeman_name))
            elif selected_map.get("id") is not None:
                out = switch_map_by_numeric_id(int(selected_map["id"]))
            else:
                print("Selected map has no usable name or id.")
                sys.exit(1)

        elif u.isdigit():
            out = switch_map_by_numeric_id(int(u))

        elif u:
            out = switch_map_by_name(u)

        else:
            print("No map selected.")
            sys.exit(1)

    if out is not None:
        print_json(out)
    else:
        sys.exit(1)