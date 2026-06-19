"""Standalone AutoXing (AXBot) REST client for map calibration.

The autoxing_bridge spellbook shadows the same module names as the Reeman
spellbook (``api_client``, ``credentials``, ...), so the Reeman adapter
process cannot import it. This client talks to the AXBot REST API (port
8090) directly with ``requests``, mirroring the endpoints used by
``autoxing_bridge/spellbook/commands/{get_current_map,get_map_overlays,
download_map}.py``. Base URL comes from env ``AUTOXING_BASE_URL``
(e.g. ``http://192.168.1.50:8090``).
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import requests

DEFAULT_TIMEOUT = float(os.environ.get("AUTOXING_HTTP_TIMEOUT", "10"))
IMAGE_TIMEOUT = 120


def base_url() -> str:
    url = os.environ.get("AUTOXING_BASE_URL", "").strip()
    if url:
        return url.rstrip("/")
    ip = os.environ.get("AUTOXING_ROBOT_IP", "").strip()
    if ip:
        return f"http://{ip}".rstrip("/")
    try:
        from autoxing_bridge._spellbook_path import ensure_spellbook

        ensure_spellbook()
        from credentials import CONSTANTS as ROBOT  # spellbook active robot

        return f"{ROBOT.PREFIX}{ROBOT.ROBOT_IP}".rstrip("/")
    except Exception:
        pass
    raise RuntimeError(
        "AUTOXING_BASE_URL is not set (e.g. http://<robot-ip>:8090) — "
        "required to fetch the AutoXing master map for calibration."
    )


def _get_json(path: str, timeout: float | None = None) -> Any | None:
    url = f"{base_url()}{path}"
    try:
        r = requests.get(url, timeout=timeout or DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (requests.exceptions.RequestException, ValueError) as exc:
        print(f"[map-tf] AutoXing GET {path} failed: {exc}", file=sys.stderr)
        return None


def get_current_map(timeout: float | None = None) -> dict | None:
    """GET /chassis/current-map — active map summary (id, uid, map_name, versions)."""
    data = _get_json("/chassis/current-map", timeout=timeout)
    return data if isinstance(data, dict) else None


def fetch_map_detail(map_id: int, timeout: float | None = None) -> dict | None:
    """GET /maps/{id} — includes ``overlays`` GeoJSON string and ``image_url``."""
    data = _get_json(f"/maps/{int(map_id)}", timeout=timeout)
    return data if isinstance(data, dict) else None


def download_map_image(map_detail: dict, dest_path: str | Path) -> str | None:
    """Save the map raster referenced by ``image_url``/``thumbnail_url`` to dest_path."""
    img = map_detail.get("image_url") or map_detail.get("thumbnail_url")
    if not img:
        print("[map-tf] No image_url/thumbnail_url in AutoXing map detail.", file=sys.stderr)
        return None
    root = base_url()
    if img.startswith(("http://", "https://")):
        img_url = img
    else:
        img_url = f"{root}/{img.lstrip('/')}"
    try:
        r = requests.get(img_url, timeout=IMAGE_TIMEOUT)
        r.raise_for_status()
        path = Path(dest_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return str(path)
    except requests.exceptions.RequestException as exc:
        print(f"[map-tf] AutoXing map image download failed: {exc}", file=sys.stderr)
        return None


# --- Overlay parsing, replicated from autoxing_bridge get_map_overlays.py ---
# (pure functions; kept in sync by hand — the spellbook module can't be
# imported here, see module docstring)


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
    """Return world (x, y) and optional orientation from GeoJSON geometry + props."""
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
        out.append(
            {
                "name": feature_label(props, kind),
                "kind": kind,
                "x": x,
                "y": y,
                "ori": 0.0 if ori is None else float(ori),
            }
        )
    return out
