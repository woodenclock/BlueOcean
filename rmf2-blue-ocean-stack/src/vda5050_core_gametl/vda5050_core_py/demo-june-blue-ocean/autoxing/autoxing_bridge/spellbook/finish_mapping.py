#!/usr/bin/env python3
"""PATCH /mappings/current — finish or cancel the active mapping session."""

from __future__ import annotations

import argparse
import sys

from api_client import parse_json_file, print_json, request_api


def finish_mapping(body: dict) -> dict | None:
    data = request_api("PATCH", "/mappings/current", json_body=body, timeout=60)
    return data if isinstance(data, dict) else data


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="PATCH /mappings/current")
    p.add_argument("--body-file", help="full JSON body (overrides --state)")
    p.add_argument(
        "--state",
        choices=("finished", "cancelled"),
        help="finish or cancel the current session",
    )
    p.add_argument(
        "--new-map-only",
        action="store_true",
        help="when finishing, keep only the newly mapped area",
    )
    args = p.parse_args()

    if args.body_file:
        body = parse_json_file(args.body_file)
        if not isinstance(body, dict):
            print("JSON body must be an object.", file=sys.stderr)
            raise SystemExit(1)
    elif args.state:
        body = {"state": args.state}
        if args.new_map_only:
            body["new_map_only"] = True
    else:
        from cli_tables import print_indexed_choices

        print_indexed_choices(("finished", "cancelled"), value_header="state")
        u = input("Select action [0–1]: ").strip()
        if u == "0":
            body = {"state": "finished"}
        elif u == "1":
            body = {"state": "cancelled"}
        else:
            print("Need --state finished|cancelled or --body-file", file=sys.stderr)
            raise SystemExit(1)
        if args.new_map_only:
            body["new_map_only"] = True

    result = finish_mapping(body)
    if result is not None:
        print_json(result)
    else:
        raise SystemExit(1)
