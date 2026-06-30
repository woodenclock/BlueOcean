#!/usr/bin/env python3

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT

from get_current_map import current_map_id, get_current_map
from get_map_overlays import extract_navigation_points, fetch_map_detail


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_waypoints(timeout: float | None = None) -> list | None:
    """Get Reeman calibrated waypoints via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/position",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json()

        waypoints = data.get("waypoints")
        if waypoints is None:
            return []

        normalized = []
        for wp in waypoints:
            pose = wp.get("pose") or {}

            normalized.append(
                {
                    "name": wp.get("name"),
                    "type": wp.get("type"),
                    "x": pose.get("x"),
                    "y": pose.get("y"),
                    "theta": pose.get("theta"),
                    "pose": pose,
                    # "raw": wp,
                }
            )

        return normalized
    
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_waypoints(
    map_id: int | None = None,
    timeout: float | None = None,
) -> list | None:
    # """Navigation targets from active map overlays (landmarks / chargers / barcodes).

    # AXBot does not expose a named-waypoint REST list — this parses ``overlays``
    # GeoJSON from ``GET /maps/{id}``.
    # """
    """
    Get navigation targets.

    Reeman FlyBoat uses REST API.
    Existing OpenAPI/WebSocket/overlay path is kept as fallback.

    AXBot does not expose a named-waypoint REST list — this parses ``overlays``
    GeoJSON from ``GET /maps/{id}``.
    """

    reeman_waypoints = get_reeman_waypoints(timeout=timeout)
    if reeman_waypoints is not None:
        return reeman_waypoints
    
    if map_id is None:
        mid = current_map_id()
    else:
        mid = int(map_id)
        if mid < 0:
            mid = current_map_id()

    if mid is None:
        print("Cannot resolve map id — load a map first (switch_map).")
        return None
    
    detail = fetch_map_detail(mid)
    if detail is None:
        return None
    
    return extract_navigation_points(detail)


if __name__ == "__main__":
    import sys

    m: int | None = None
    if len(sys.argv) > 1 and sys.argv[1].strip().lstrip("-").isdigit():
        m = int(sys.argv[1])
    if m is None:
        cm = get_current_map()
        if cm:
            print("Current map:", cm.get("map_name"), "id:", cm.get("id"))
        wps = get_waypoints()
    else:
        wps = get_waypoints(m)
    if wps is not None:
        if wps:
            try:
                from cli_tables import print_waypoints_table
                print_waypoints_table(wps)
            except Exception:
                print_json(wps)
        else:
            print("No waypoints in current map overlays.")
