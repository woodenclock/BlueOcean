#!/usr/bin/env python3

import base64
from pathlib import Path

import requests
import yaml

from api_client import base_url, request_api
from credentials import CONSTANTS as ROBOT

REQUEST_TIMEOUT = 120
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Standard ROS map_server occupancy thresholds (Reeman PNG follows the same convention).
_OCCUPIED_THRESH = 0.65
_FREE_THRESH = 0.196


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def normalize_dest_path(dest_path: str) -> Path:
    """Resolve relative paths under cwd; append ``.png`` when no image extension."""
    path = Path(dest_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.suffix.lower() not in _IMAGE_SUFFIXES:
        path = path.with_suffix(".png")
    return path


def get_reeman_current_map(timeout: float | None = None) -> dict | None:
    """Get Reeman current map info via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/current_map",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, dict):
            return None

        return data
    except Exception as e:
        print(f"Reeman current map REST error: {e}")
        return None


def get_reeman_map(timeout: float | None = None) -> dict | None:
    """GET /reeman/map — structured current map (base64 PNG + resolution/origin)."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/map",
            timeout=timeout or 10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"Reeman map REST error: {e}")
        return None


def write_map_yaml(meta: dict, image_path: Path) -> Path:
    """Write a ROS map_server-compatible ``.yaml`` sidecar next to ``image_path``.

    Top-level keys (``image``/``resolution``/``origin``/...) follow the ROS
    map_server format so the bundle can be consumed by standard tooling. Reeman
    map detail fields are preserved under ``reeman`` for round-tripping.
    """
    res = meta.get("resolution")
    origin_x = meta.get("origin_x")
    origin_y = meta.get("origin_y")

    doc: dict = {
        "image": image_path.name,
        "resolution": res if res is not None else 0.05,
        "origin": [
            origin_x if origin_x is not None else 0.0,
            origin_y if origin_y is not None else 0.0,
            0.0,
        ],
        "negate": 0,
        "occupied_thresh": _OCCUPIED_THRESH,
        "free_thresh": _FREE_THRESH,
        "reeman": {
            "name": meta.get("name"),
            "alias": meta.get("alias"),
            "width": meta.get("width"),
            "height": meta.get("height"),
        },
    }

    yaml_path = image_path.with_suffix(".yaml")
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return yaml_path


def download_reeman_map(
    dest_path: str,
    map_name: str | None = None,
    *,
    timeout: float | None = None,
) -> str | None:
    """Download Reeman map export raster via REST API (no metadata, fallback only).

    Reeman endpoint:
        POST /download/export_map
        body: {"name": "<map name>"}

    Returns path written, or None.
    """
    try:
        if not map_name:
            current = get_reeman_current_map(timeout=timeout)
            if not current:
                return None

            map_name = current.get("name") or current.get("alias")

        if not map_name:
            print("No valid Reeman map name.")
            return None

        resp = requests.post(
            f"{_robot_base_url()}/download/export_map",
            json={"name": map_name},
            timeout=timeout or REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        path = normalize_dest_path(dest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        return str(path)

    except Exception as e:
        print(f"Reeman map download REST error: {e}")
        return None


def download_openapi_map(
    dest_path: str,
    map_id: int | None = None,
    *,
    prefer: str = "image_url",
) -> str | None:
    """Fetch map raster from GET /maps/{id} image_url or thumbnail_url (fallback only).

    Returns path written, or None.
    """
    if map_id is None:
        from get_current_map import current_map_id

        mid = current_map_id()
    else:
        mid = int(map_id)

    if mid is None or mid < 0:
        print("No valid map id.")
        return None

    meta = request_api("GET", f"/maps/{mid}", timeout=REQUEST_TIMEOUT)
    if not isinstance(meta, dict):
        return None

    if prefer == "thumbnail_url":
        img = meta.get("thumbnail_url") or meta.get("image_url")
    else:
        img = meta.get("image_url") or meta.get("thumbnail_url")

    if not img:
        print("No image_url/thumbnail_url in map detail.")
        return None

    root = base_url()
    if img.startswith("/"):
        img_url = f"{root.rstrip('/')}{img}"
    elif img.startswith("http://") or img.startswith("https://"):
        img_url = img
    else:
        img_url = f"{root.rstrip('/')}/{img.lstrip('/')}"

    try:
        ir = requests.get(img_url, timeout=REQUEST_TIMEOUT)
        ir.raise_for_status()

        path = normalize_dest_path(dest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(ir.content)
        return str(path)

    except requests.exceptions.RequestException as e:
        print(f"OpenAPI map download failed: {e}")
        return None


def download_map(
    dest_path: str,
    map_name: str | None = None,
    *,
    prefer: str = "image_url",
    write_yaml: bool = True,
) -> str | None:
    """Save the current Reeman map raster (``.png``) and a ROS ``.yaml`` sidecar.

    Fetches ``GET /reeman/map`` for the base64 PNG plus resolution/origin,
    writes the PNG, and — when ``write_yaml`` — writes a ROS-compatible
    ``.yaml`` sidecar describing resolution/origin and Reeman metadata. Falls
    back to the export_map / OpenAPI raster (no YAML) when the structured map
    is unavailable.

    Returns the PNG path written, or ``None``.
    """
    meta = get_reeman_map()
    img = meta.get("image_url") if isinstance(meta, dict) else None

    if img and str(img).startswith("data:image/png;base64,"):
        png_bytes = base64.b64decode(str(img).split(",", 1)[1])
        path = normalize_dest_path(dest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png_bytes)

        if write_yaml:
            try:
                yaml_path = write_map_yaml(meta, path)
                print("Saved map info:", yaml_path)
            except OSError as e:
                print(f"Map info (.yaml) write failed: {e}")

        return str(path)

    # Fallback: raw raster only (no metadata available for the YAML sidecar).
    saved = download_reeman_map(dest_path, map_name=map_name)
    if saved is not None:
        return saved

    return download_openapi_map(dest_path, prefer=prefer)


def _default_filename(map_id: int | str, map_name: str | None = None) -> str:
    if map_name and map_name.strip():
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in map_name.strip())
        safe = safe.strip("._") or f"map_{map_id}"
        return safe
    return f"map_{map_id}"


if __name__ == "__main__":
    import sys

    use_current = False
    argv = []
    for a in sys.argv[1:]:
        if a in ("--current", "-c"):
            use_current = True
        else:
            argv.append(a)

    out = argv[0] if argv else ""
    chosen_name: str | None = None
    map_name: str | None = None

    current = get_reeman_current_map()
    if current:
        chosen_name = current.get("alias") or current.get("name")
        map_name = current.get("name") or chosen_name

    if not out:
        default = _default_filename(map_name or "current", chosen_name)
        if use_current:
            out = default  # --current: download immediately, no prompt
        else:
            out = (
                input(f"Output filename in current dir [{default}]: ").strip() or default
            )

    saved = download_map(out, map_name)
    if saved:
        print("Saved:", saved)
    else:
        sys.exit(1)
