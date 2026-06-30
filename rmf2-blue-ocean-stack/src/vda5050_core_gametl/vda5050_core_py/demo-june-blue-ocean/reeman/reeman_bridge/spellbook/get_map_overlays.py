#!/usr/bin/env python3

import base64
import json
import math
from pathlib import Path

import requests

from api_client import print_json, request_api
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


# -------------------------
# Reeman REST API support
# -------------------------

def get_reeman_current_map(timeout: float | None = None) -> dict | None:
    """GET /reeman/current_map."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/current_map",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_reeman_map(timeout: float | None = None) -> dict | None:
    """GET /reeman/map."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/map",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_reeman_navigation_points(timeout: float | None = None) -> list[dict] | None:
    """GET /reeman/position and convert Reeman waypoints into spellbook waypoint format."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/position",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        data = resp.json()

        waypoints = data.get("waypoints")
        if not isinstance(waypoints, list):
            return []

        out: list[dict] = []
        for wp in waypoints:
            if not isinstance(wp, dict):
                continue

            pose = wp.get("pose")
            if not isinstance(pose, dict):
                continue

            name = str(wp.get("name") or "point")
            reeman_type = str(wp.get("type") or "normal")

            kind = {
                "charge": "charger",
                "delivery": "landmark",
                "normal": "landmark",
                "production": "landmark",
                "avoid": "landmark",
                "avoidance": "landmark",
                "temporary": "landmark",
                "recycle": "landmark",
                "waypoint": "landmark",
            }.get(reeman_type, "landmark")

            item = {
                "name": name,
                "kind": kind,
                "x": float(pose.get("x", 0.0)),
                "y": float(pose.get("y", 0.0)),
                "ori": float(pose.get("theta", 0.0)),
                "reeman_type": reeman_type,
            }
            out.append(item)

        return out
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_map_overlays(timeout: float | None = None) -> list[dict] | None:
    """
    Get map navigation points.

    Reeman FlyBoat uses REST API.
    Existing OpenAPI REST path is kept as fallback.
    """
    pts = get_reeman_navigation_points(timeout=timeout)
    if pts is not None:
        return pts

    return None


# -------------------------
# Map download helpers
# -------------------------

def _safe_name(name: str | None, fallback: str = "reeman_map") -> str:
    raw = str(name or fallback).strip() or fallback
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in raw)


def _map_base_name(reeman_map_info: dict | None, map_data: dict | None = None) -> str:
    if isinstance(reeman_map_info, dict):
        return _safe_name(
            reeman_map_info.get("alias")
            or reeman_map_info.get("name")
            or reeman_map_info.get("map_alias")
            or reeman_map_info.get("map_name")
        )

    if isinstance(map_data, dict):
        width = map_data.get("width", "unknown")
        height = map_data.get("height", "unknown")
        return _safe_name(f"reeman_map_{width}x{height}")

    return "reeman_map"


def save_base64_url(map_data: dict, output_path: str) -> None:
    image_url = map_data.get("image_url")
    if not image_url:
        raise ValueError("Map data does not contain image_url")

    path = Path(output_path)
    path.write_text(str(image_url), encoding="utf-8")
    print(f"Saved Base64 URL: {path}")


def save_image_url_png(map_data: dict, output_path: str) -> None:
    image_url = map_data.get("image_url")

    if not image_url:
        raise ValueError("Map data does not contain image_url")

    if not str(image_url).startswith("data:image/png;base64,"):
        raise ValueError("image_url is not a PNG base64 data URL")

    base64_data = str(image_url).split(",", 1)[1]
    png_bytes = base64.b64decode(base64_data)

    path = Path(output_path)
    path.write_bytes(png_bytes)

    print(f"Saved PNG: {path}")
    print(f"Map size: {map_data.get('width')} x {map_data.get('height')}")
    print(f"Resolution: {map_data.get('resolution')}")


def save_yaml(map_data: dict, output_path: str, image_path: str) -> None:
    resolution = map_data.get("resolution")
    origin_x = map_data.get("origin_x", 0.0)
    origin_y = map_data.get("origin_y", 0.0)

    if resolution is None:
        raise ValueError("Map data does not contain resolution")

    yaml_text = (
        f"image: {image_path}\n"
        f"resolution: {resolution}\n"
        f"origin: [{origin_x}, {origin_y}, 0.0]\n"
        f"negate: 0\n"
        f"occupied_thresh: 0.65\n"
        f"free_thresh: 0.196\n"
    )

    path = Path(output_path)
    path.write_text(yaml_text, encoding="utf-8")
    print(f"Saved YAML: {path}")


def ask_download_format() -> int | None:
    print()
    print("+-------+------------+")
    print("| Index | Download   |")
    print("+-------+------------+")
    print("| 0     | Base64 URL |")
    print("| 1     | PNG        |")
    print("| 2     | YAML + PNG |")
    print("+-------+------------+")
    print()

    choice = input("Download map? Select [0/1/2], or press Enter to skip: ").strip()

    if choice == "":
        return None

    if choice in {"0", "1", "2"}:
        return int(choice)

    print("Invalid input. Skipping download.")
    return None


def handle_reeman_map_download(reeman_map_info: dict | None) -> None:
    choice = ask_download_format()
    if choice is None:
        return

    map_data = get_reeman_map()
    if not map_data:
        print("Failed to get Reeman map data.")
        return

    base_name = _map_base_name(reeman_map_info, map_data)

    if choice == 0:
        save_base64_url(map_data, f"{base_name}_base64_url.txt")
        return

    if choice == 1:
        save_image_url_png(map_data, f"{base_name}.png")
        return

    if choice == 2:
        png_name = f"{base_name}.png"
        yaml_name = f"{base_name}.yaml"
        save_image_url_png(map_data, png_name)
        save_yaml(map_data, yaml_name, png_name)
        return


# -------------------------
# Existing AXBot fallback
# -------------------------

def fetch_map_detail(map_id: int) -> dict | None:
    """GET /maps/{id} — includes ``overlays`` GeoJSON string."""
    data = request_api("GET", f"/maps/{int(map_id)}")
    return data if isinstance(data, dict) else None


def parse_overlays_string(overlays: str | None) -> dict | None:
    if not overlays or not str(overlays).strip():
        return None
    try:
        obj = json.loads(overlays)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _centroid_ring(ring: list) -> tuple[float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for pt in ring:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))
    if not xs:
        return 0.0, 0.0
    return sum(xs) / len(xs), sum(ys) / len(ys)


def geom_to_xy_ori(geom: dict, props: dict) -> tuple[float, float, float | None]:
    """Return world (x, y) and optional orientation from GeoJSON geometry + AXBot overlay props."""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    ori = props.get("yaw")
    if ori is None:
        ori = props.get("orientation")
    try:
        ori_f = float(ori) if ori is not None else None
    except (TypeError, ValueError):
        ori_f = None

    if gtype == "Point" and isinstance(coords, list) and len(coords) >= 2:
        return float(coords[0]), float(coords[1]), ori_f

    if gtype == "LineString" and isinstance(coords, list) and len(coords) >= 1:
        mid = coords[len(coords) // 2]
        if isinstance(mid, (list, tuple)) and len(mid) >= 2:
            i0 = max(0, len(coords) // 2 - 1)
            a, b = coords[i0], coords[min(i0 + 1, len(coords) - 1)]
            dx, dy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
            line_ori = math.atan2(dy, dx) if dx or dy else None
            return float(mid[0]), float(mid[1]), ori_f if ori_f is not None else line_ori

    if gtype == "Polygon" and isinstance(coords, list) and coords:
        ring = coords[0]
        cx, cy = _centroid_ring(ring)
        return cx, cy, ori_f

    return 0.0, 0.0, ori_f


def overlay_feature_kind(props: dict) -> str | None:
    """Return ``landmark``, ``charger``, ``barcode``, or None."""
    pt = props.get("type")
    if pt is not None:
        s = str(pt)
        if s in ("39", "9", "37"):
            return {"39": "landmark", "9": "charger", "37": "barcode"}[s]
    return None


def feature_label(props: dict, kind: str) -> str:
    if kind == "landmark":
        return str(
            props.get("landmarkId")
            or props.get("name")
            or props.get("label")
            or props.get("id")
            or "landmark",
        )
    if kind == "charger":
        return f"charger_{props.get('dockingPointId', props.get('deviceIds', '?'))}"
    if kind == "barcode":
        return f"barcode_{props.get('barcodeId', '?')}"
    return "point"


def extract_navigation_points(map_detail: dict) -> list[dict]:
    """Points from map overlays: landmarks (39), chargers (9), barcodes (37)."""
    out: list[dict] = []
    raw = map_detail.get("overlays")
    fc = parse_overlays_string(raw if isinstance(raw, str) else None)
    if not fc:
        return out

    features = fc.get("features")
    if not isinstance(features, list):
        return out

    for f in features:
        if not isinstance(f, dict):
            continue

        props = f.get("properties")
        geom = f.get("geometry")
        if not isinstance(props, dict) or not isinstance(geom, dict):
            continue

        kind = overlay_feature_kind(props)
        if not kind:
            continue

        x, y, ori = geom_to_xy_ori(geom, props)
        name = feature_label(props, kind)
        use_ori = 0.0 if ori is None else float(ori)

        item = {"name": name, "kind": kind, "x": x, "y": y, "ori": use_ori}
        fid = f.get("id")
        if fid is not None:
            item["feature_id"] = fid

        out.append(item)

    return out


if __name__ == "__main__":
    import sys

    from cli_tables import print_maps_table, print_waypoints_table
    from get_maps import get_maps

    # Reeman first
    reeman_map = get_reeman_current_map()
    reeman_pts = get_reeman_navigation_points()

    if reeman_pts is not None:
        print_json(
            {
                "backend": "reeman_rest",
                "map_name": reeman_map.get("name") if isinstance(reeman_map, dict) else None,
                "map_alias": reeman_map.get("alias") if isinstance(reeman_map, dict) else None,
                "points": len(reeman_pts),
            }
        )

        print(f"Extracted navigation points: {len(reeman_pts)}")
        if reeman_pts:
            shown = print_waypoints_table(reeman_pts, limit=30)
            if len(reeman_pts) > shown:
                print(f"... and {len(reeman_pts) - shown} more")

        handle_reeman_map_download(reeman_map)
        sys.exit(0)

    # Existing OpenAPI REST fallback
    mid: int | None = None
    if len(sys.argv) > 1 and sys.argv[1].strip().isdigit():
        mid = int(sys.argv[1])
    else:
        maps = get_maps() or []
        if not maps:
            print("No maps or GET /maps/ failed.")
            sys.exit(1)

        print_maps_table(maps)
        choice = input("Map index (or id number): ").strip()
        if choice.isdigit() and int(choice) < len(maps):
            mid = int(maps[int(choice)].get("id"))
        elif choice.isdigit():
            mid = int(choice)

    if mid is None:
        print("No map id.")
        sys.exit(1)

    detail = fetch_map_detail(mid)
    if detail:
        print_json(
            {
                "backend": "openapi_fallback",
                "id": detail.get("id"),
                "map_name": detail.get("map_name"),
                "overlays_len": len(str(detail.get("overlays") or "")),
            }
        )

        pts = extract_navigation_points(detail)
        print(f"Extracted navigation points: {len(pts)}")
        if pts:
            shown = print_waypoints_table(pts, limit=30)
            if len(pts) > shown:
                print(f"... and {len(pts) - shown} more")