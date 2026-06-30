#!/usr/bin/env python3

import sys

from api_client import request_api


def delete_map(map_id: int) -> bool:
    """DELETE /maps/{id}."""
    data = request_api("DELETE", f"/maps/{int(map_id)}")
    return data is not None


if __name__ == "__main__":
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not arg.isdigit():
        print("Usage: delete_map <numeric_map_id>")
        sys.exit(1)
    mid = int(arg)
    c = input(f"Permanently delete map id={mid}? [y/N]: ").strip().lower()
    if c not in ("y", "yes"):
        print("Aborted.")
        sys.exit(1)
    if delete_map(mid):
        print(f"Deleted map id={mid}.")
    else:
        sys.exit(1)
