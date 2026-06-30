#!/usr/bin/env python3
"""POST /maps/ — create a map (Base64, robot file paths, or from mapping_id)."""

from __future__ import annotations

import argparse
import json
import sys

from api_client import parse_json_file, print_json, request_api


def create_map(body: dict) -> dict | None:
    data = request_api("POST", "/maps/", json_body=body, timeout=120)
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="POST /maps/ — body from --body-file or --body (see openapi CreateMapFrom*)",
    )
    p.add_argument("--body-file", help="JSON request body file")
    p.add_argument("--body", help="JSON request body string")
    args = p.parse_args()

    if args.body_file:
        body = parse_json_file(args.body_file)
    elif args.body:
        body = json.loads(args.body)
    else:
        p.error("one of --body-file or --body is required")

    if not isinstance(body, dict):
        print("JSON body must be an object.", file=sys.stderr)
        raise SystemExit(1)

    result = create_map(body)
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
