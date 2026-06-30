#!/usr/bin/env python3
"""POST /mappings/ — start a mapping session."""

from __future__ import annotations

import argparse
import json
import sys

from api_client import parse_json_file, print_json, request_api


def start_mapping(body: dict) -> dict | None:
    data = request_api("POST", "/mappings/", json_body=body, timeout=60)
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="POST /mappings/ — start mapping")
    p.add_argument("--body-file", help="full JSON body (overrides flags)")
    p.add_argument(
        "--continue-mapping",
        action="store_true",
        help="continue from a previous mapping session",
    )
    p.add_argument(
        "--start-pose-type",
        choices=("zero", "current_pose"),
        help="initial pose for the session",
    )
    args = p.parse_args()

    if args.body_file:
        body = parse_json_file(args.body_file)
        if not isinstance(body, dict):
            print("JSON body must be an object.", file=sys.stderr)
            raise SystemExit(1)
    else:
        body = {}
        if args.continue_mapping:
            body["continue_mapping"] = True
        if args.start_pose_type:
            body["start_pose_type"] = args.start_pose_type

    result = start_mapping(body)
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
