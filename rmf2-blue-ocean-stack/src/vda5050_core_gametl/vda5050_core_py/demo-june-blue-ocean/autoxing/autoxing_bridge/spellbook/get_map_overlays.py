#!/usr/bin/env python3

import json
import math

from api_client import print_json, request_api


def fetch_map_detail(map_id: int) -> dict | None:
    """GET /maps/{id} — includes ``overlays`` GeoJSON string."""
    data = request_api("GET", f"/maps/{int(map_id)}")
    return data if isinstance(data, dict) else None


def map_detail_summary(detail: dict) -> dict:
    """Key fields from GET /maps/{id} (origin, resolution, URLs) without raw overlays."""
    fc = parse_overlays_string(
        detail.get("overlays") if isinstance(detail.get("overlays"), str) else None
    )
    feature_count = len(fc.get("features", [])) if fc else 0
    return {
        "id": detail.get("id"),
        "map_name": detail.get("map_name"),
        "uid": detail.get("uid"),
        "map_version": detail.get("map_version"),
        "create_time": detail.get("create_time"),
        "last_modified_time": detail.get("last_modified_time"),
        "grid_origin_x": detail.get("grid_origin_x"),
        "grid_origin_y": detail.get("grid_origin_y"),
        "grid_resolution": detail.get("grid_resolution"),
        "overlays_version": detail.get("overlays_version"),
        "overlays_feature_count": feature_count,
        "overlays_len": len(str(detail.get("overlays") or "")),
        "thumbnail_url": detail.get("thumbnail_url"),
        "image_url": detail.get("image_url"),
        "download_url": detail.get("download_url"),
        "pbstream_url": detail.get("pbstream_url"),
    }


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
            # heading along segment
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
    lt = props.get("lineType")
    rt = props.get("regionType")
    _ = (lt, rt)  # virtual walls etc. — not navigation points for this spellbook
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
        print_json(map_detail_summary(detail))
        pts = extract_navigation_points(detail)
        print(f"Extracted navigation points: {len(pts)}")
        if pts:
            shown = print_waypoints_table(pts, limit=30)
            if len(pts) > shown:
                print(f"... and {len(pts) - shown} more")
