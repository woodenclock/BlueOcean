#!/usr/bin/env python3
"""
Get map data via Reeman REST ``GET /reeman/map``.

Usage:
    get_map_ws
    get_map_ws --save-png map.png
    get_map_ws --save-yaml map.yaml
    get_map_ws --save-json map.json
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import requests

from api_client import print_json
from credentials import CONSTANTS as ROBOT


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


def get_reeman_map(timeout: float | None = None) -> dict | None:
    """Get Reeman current map via REST API."""
    try:
        resp = requests.get(
            f"{_robot_base_url()}/reeman/map",
            timeout=timeout or 5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Reeman REST error: {e}")
        return None


def get_map_ws(timeout: float | None = None) -> dict | None:
    """Get map data (Reeman FlyBoat REST only)."""
    return get_reeman_map(timeout=timeout)


def save_image_url_png(state: dict, output_path: str) -> None:
    image_url = state.get("image_url")

    if not image_url:
        raise ValueError("Map data does not contain image_url")

    if not image_url.startswith("data:image/png;base64,"):
        raise ValueError("image_url is not a PNG base64 data URL")

    base64_data = image_url.split(",", 1)[1]
    png_bytes = base64.b64decode(base64_data)

    path = Path(output_path)
    path.write_bytes(png_bytes)

    width = state.get("width")
    height = state.get("height")
    resolution = state.get("resolution")

    print(f"Saved PNG: {path}")
    print(f"Map size: {width} x {height}")
    print(f"Resolution: {resolution}")


def save_yaml(state: dict, output_path: str, image_path: str) -> None:
    resolution = state.get("resolution")
    origin_x = state.get("origin_x", 0.0)
    origin_y = state.get("origin_y", 0.0)

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


def save_json(state: dict, output_path: str) -> None:
    path = Path(output_path)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Saved JSON: {path}")


def ask_output_format() -> int:
    print()
    print("+-------+------------+")
    print("| Index | Format     |")
    print("+-------+------------+")
    print("| 0     | Base64 URL |")
    print("| 1     | PNG        |")
    print("| 2     | YAML + PNG |")
    print("+-------+------------+")
    print()

    while True:
        choice = input("Select map output format [0/1/2]: ").strip()

        if choice in {"0", "1", "2"}:
            return int(choice)

        print("Invalid input. Please enter 0, 1, or 2.")


def default_png_name(state: dict) -> str:
    width = state.get("width", "unknown")
    height = state.get("height", "unknown")
    return f"reeman_map_{width}x{height}.png"


def default_yaml_name(state: dict) -> str:
    width = state.get("width", "unknown")
    height = state.get("height", "unknown")
    return f"reeman_map_{width}x{height}.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Get Reeman map data")
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--save-png", type=str, default=None)
    parser.add_argument("--save-yaml", type=str, default=None)
    parser.add_argument("--save-json", type=str, default=None)
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not ask output format; print JSON unless save options are used",
    )

    args = parser.parse_args()

    state = get_map_ws(timeout=args.timeout)

    if state is None:
        sys.exit(1)

    if args.save_json:
        save_json(state, args.save_json)

    if args.save_png:
        save_image_url_png(state, args.save_png)

    if args.save_yaml:
        png_path = Path(args.save_yaml).with_suffix(".png")
        save_image_url_png(state, str(png_path))
        save_yaml(state, args.save_yaml, png_path.name)

    if args.save_json or args.save_png or args.save_yaml:
        return

    if args.no_prompt:
        print_json(state)
        return

    choice = ask_output_format()

    if choice == 0:
        print_json(state)
        return

    if choice == 1:
        png_path = default_png_name(state)
        save_image_url_png(state, png_path)
        return

    if choice == 2:
        png_path = default_png_name(state)
        yaml_path = default_yaml_name(state)

        save_image_url_png(state, png_path)
        save_yaml(state, yaml_path, png_path)


if __name__ == "__main__":
    main()
