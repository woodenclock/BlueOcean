#!/usr/bin/env python3

from pathlib import Path

import requests
import yaml

from api_client import base_url, request_api

REQUEST_TIMEOUT = 120
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Standard ROS map_server occupancy thresholds (AXBot PNG follows the same convention).
_OCCUPIED_THRESH = 0.65
_FREE_THRESH = 0.196


def normalize_dest_path(dest_path: str) -> Path:
    """Resolve relative paths under cwd; append ``.png`` when no image extension."""
    path = Path(dest_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.suffix.lower() not in _IMAGE_SUFFIXES:
        path = path.with_suffix(".png")
    return path


def _resolve_url(img: str) -> str:
    """Turn a relative or absolute ``image_url`` into a fully-qualified URL."""
    root = base_url()
    if img.startswith("/"):
        return f"{root.rstrip('/')}{img}"
    if img.startswith("http://") or img.startswith("https://"):
        return img
    return f"{root.rstrip('/')}/{img.lstrip('/')}"


def write_map_yaml(meta: dict, image_path: Path) -> Path:
    """Write a ROS map_server-compatible ``.yaml`` sidecar next to ``image_path``.

    Top-level keys (``image``/``resolution``/``origin``/...) follow the ROS
    map_server format so the bundle can be consumed by standard tooling. AXBot
    map detail fields are preserved under ``axbot`` for round-tripping.
    """
    res = meta.get("grid_resolution")
    origin_x = meta.get("grid_origin_x")
    origin_y = meta.get("grid_origin_y")

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
        "axbot": {
            "id": meta.get("id"),
            "uid": meta.get("uid"),
            "map_name": meta.get("map_name") or meta.get("name"),
            "map_version": meta.get("map_version"),
            "overlays_version": meta.get("overlays_version"),
            "create_time": meta.get("create_time"),
            "last_modified_time": meta.get("last_modified_time"),
            "image_url": meta.get("image_url"),
            "thumbnail_url": meta.get("thumbnail_url"),
            "pbstream_url": meta.get("pbstream_url"),
            "overlays": meta.get("overlays"),
        },
    }

    yaml_path = image_path.with_suffix(".yaml")
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return yaml_path


def download_map(
    dest_path: str,
    map_id: int | None = None,
    *,
    prefer: str = "image_url",
    write_yaml: bool = True,
) -> str | None:
    """Save map info (``.yaml``) and the full-resolution raster (``.png``).

    Fetches ``GET /maps/{id}`` for the detail, downloads ``image_url``
    (or ``thumbnail_url``), and — when ``write_yaml`` — writes a ROS-compatible
    ``.yaml`` sidecar describing resolution/origin and AXBot metadata.

    Returns the PNG path written, or ``None``.
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

    img_url = _resolve_url(img)

    try:
        ir = requests.get(img_url, timeout=REQUEST_TIMEOUT)
        ir.raise_for_status()
        path = normalize_dest_path(dest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(ir.content)
    except requests.exceptions.RequestException as e:
        print(f"Download failed: {e}")
        return None

    if write_yaml:
        try:
            yaml_path = write_map_yaml(meta, path)
            print("Saved map info:", yaml_path)
        except OSError as e:
            print(f"Map info (.yaml) write failed: {e}")

    return str(path)


def _default_filename(map_id: int, map_name: str | None = None) -> str:
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
    mid: int | None = None
    chosen_name: str | None = None

    if len(argv) > 1 and argv[1].strip().lstrip("-").isdigit():
        mid = int(argv[1])
    elif len(argv) == 1 and out.isdigit():
        mid = int(out)
        out = f"map_{mid}.png"

    if mid is None and use_current:
        from get_current_map import current_map_id, get_current_map

        cm = get_current_map()
        mid = current_map_id(cm)
        if mid is None:
            print("No active map in the library (current map id is unavailable).")
            sys.exit(1)
        chosen_name = (cm or {}).get("name") or (cm or {}).get("map_name")

    if mid is None:
        from cli_tables import print_maps_table
        from get_maps import get_maps

        maps = get_maps() or []
        if not maps:
            print("No maps.")
            sys.exit(1)
        print_maps_table(maps)
        u = input("Map index (or enter map id): ").strip()
        if u.isdigit() and int(u) < len(maps):
            chosen = maps[int(u)]
            mid = int(chosen["id"])
            chosen_name = chosen.get("name")
        elif u.isdigit():
            mid = int(u)
        else:
            print("Invalid selection.")
            sys.exit(1)

    if not out:
        default = _default_filename(mid, chosen_name)
        if use_current:
            out = default  # --current: download immediately, no prompt
        else:
            out = (
                input(f"Output filename in current dir [{default}]: ").strip() or default
            )

    saved = download_map(out, mid)
    if saved:
        print("Saved:", saved)
    else:
        sys.exit(1)
