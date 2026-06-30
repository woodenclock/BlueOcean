#!/usr/bin/env python3
"""GET /services/get_nav_thumbnail — 200×200 nav composite when firmware supports it."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from api_client import request_api


def main() -> None:
    p = argparse.ArgumentParser(description="GET /services/get_nav_thumbnail")
    p.add_argument(
        "--png-out",
        help="decode map.data PNG to this path",
    )
    p.add_argument("--json-out", help="write full JSON response here")
    args = p.parse_args()

    blob = request_api("GET", "/services/get_nav_thumbnail")
    if not isinstance(blob, dict):
        print("Unexpected response", blob, file=sys.stderr)
        sys.exit(1)
    inner = blob.get("map") or {}
    b64 = inner.get("data")
    if args.png_out and isinstance(b64, str) and b64.strip():
        Path(args.png_out).write_bytes(base64.standard_b64decode(b64))
        print(f"Wrote PNG to {args.png_out}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(blob, indent=2), encoding="utf-8")
        print(f"Wrote JSON to {args.json_out}")
    if not args.png_out and not args.json_out:
        preview = dict(blob)
        if isinstance(inner.get("data"), str) and len(inner["data"]) > 80:
            prev_map = dict(inner)
            prev_map["data"] = f"<base64 PNG, {len(inner['data'])} chars>"
            preview["map"] = prev_map
        print(json.dumps(preview, indent=2))


if __name__ == "__main__":
    main()
