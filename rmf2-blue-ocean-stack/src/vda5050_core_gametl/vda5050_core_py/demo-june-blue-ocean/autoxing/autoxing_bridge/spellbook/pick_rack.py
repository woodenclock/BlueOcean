#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import sys
import time
from typing import Any

from api_client import print_json, request_api
from navigate import monitor_move_after_dispatch


RACK_POINT_TYPE = "34"


def get_current_map() -> dict[str, Any]:
    maps = request_api("GET", "/maps/")

    if not isinstance(maps, list) or not maps:
        raise SystemExit("Could not get maps from /maps/")

    # Your current map BlueOcean is first in /maps/
    current_map_id = maps[0]["id"]

    current_map = request_api("GET", f"/maps/{current_map_id}")

    if not isinstance(current_map, dict):
        raise SystemExit(f"Could not get map {current_map_id}")

    return current_map


def get_rack_points() -> dict[str, dict[str, float]]:
    current_map = get_current_map()

    overlays_raw = current_map.get("overlays")
    if not isinstance(overlays_raw, str):
        raise SystemExit("Map has no overlays string.")

    overlays = json.loads(overlays_raw)
    features = overlays.get("features", [])

    rack_points: dict[str, dict[str, float]] = {}

    for feature in features:
        if not isinstance(feature, dict):
            continue

        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})

        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            continue

        if properties.get("type") != RACK_POINT_TYPE:
            continue

        name = properties.get("name")
        coordinates = geometry.get("coordinates")
        yaw_deg = properties.get("yaw")

        if not name or not isinstance(coordinates, list) or len(coordinates) < 2:
            continue

        if yaw_deg is None:
            continue

        try:
            x = float(coordinates[0])
            y = float(coordinates[1])
            yaw_rad = math.radians(float(yaw_deg))
        except (TypeError, ValueError):
            continue

        rack_points[str(name)] = {
            "x": x,
            "y": y,
            "ori": yaw_rad,
        }

    if not rack_points:
        raise SystemExit("No rack points found in map overlays.")

    return dict(sorted(rack_points.items()))


def choose_rack_point(prompt: str, rack_points: dict[str, dict[str, float]]) -> str:
    names = list(rack_points.keys())

    print(f"\n{prompt}")

    for index, name in enumerate(names, start=1):
        pose = rack_points[name]
        print(
            f"{index}. {name} "
            f"(x={pose['x']:.4f}, y={pose['y']:.4f}, ori={pose['ori']:.4f})"
        )

    choice = input("\nRack point > ").strip()

    if choice in rack_points:
        return choice

    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(names):
            return names[index - 1]

    raise SystemExit("Invalid rack point selected.")


def start_rack_detection() -> dict | None:
    result = request_api(
        "POST",
        "/services/start_rack_size_detection",
        json_body={},
    )

    if result is not None:
        print_json(result)

    return result if isinstance(result, dict) else None


def align_with_rack(rack_point: str, rack_points: dict[str, dict[str, float]]) -> dict | None:
    pose = rack_points[rack_point]

    payload = {
        "creator": "pick_rack",
        "type": "align_with_rack",
        "target_x": pose["x"],
        "target_y": pose["y"],
        "target_ori": pose["ori"],
    }

    result = request_api(
        "POST",
        "/chassis/moves",
        json_body=payload,
    )

    if result is not None:
        print_json(result)

    return result if isinstance(result, dict) else None


def jack_up() -> dict | None:
    result = request_api(
        "POST",
        "/services/jack_up",
        json_body={},
    )

    if result is not None:
        print_json(result)

    return result if isinstance(result, dict) else None


def move_to_unload_point(
    rack_point: str,
    rack_points: dict[str, dict[str, float]],
) -> dict | None:
    pose = rack_points[rack_point]

    payload = {
        "creator": "pick_rack",
        "type": "to_unload_point",
        "target_x": pose["x"],
        "target_y": pose["y"],
        "target_ori": pose["ori"],
    }

    result = request_api(
        "POST",
        "/chassis/moves",
        json_body=payload,
    )

    if result is not None:
        print_json(result)

    return result if isinstance(result, dict) else None


def jack_down() -> dict | None:
    result = request_api(
        "POST",
        "/services/jack_down",
        json_body={},
    )

    if result is not None:
        print_json(result)

    return result if isinstance(result, dict) else None


def pick_and_place_rack(
    pickup_point: str,
    putdown_point: str,
    rack_points: dict[str, dict[str, float]],
) -> None:
    print(f"\n[1/7] Pickup point: {pickup_point}")
    print(f"[2/7] Putdown point: {putdown_point}")

    print("\n[3/7] Starting rack size detection...")
    start_rack_detection()
    time.sleep(3)

    print("\n[4/7] Aligning with rack...")
    result = align_with_rack(pickup_point, rack_points)

    if result is None:
        raise SystemExit("Align with rack request failed.")

    monitor_move_after_dispatch()

    print("\n[5/7] Jacking up rack...")
    jack_up()
    time.sleep(2)

    print("\n[6/7] Moving to unload point...")
    result = move_to_unload_point(putdown_point, rack_points)

    if result is None:
        raise SystemExit("Move to unload point request failed.")

    monitor_move_after_dispatch()

    print("\n[7/7] Jacking down rack...")
    jack_down()

    print("\nRack pick-and-place sequence complete.")


if __name__ == "__main__":
    try:
        rack_points = get_rack_points()

        pickup_point = choose_rack_point("Choose rack pickup point:", rack_points)
        putdown_point = choose_rack_point("Choose rack putdown point:", rack_points)

        if pickup_point == putdown_point:
            raise SystemExit("Pickup and putdown points must be different.")

        pick_and_place_rack(pickup_point, putdown_point, rack_points)

    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
