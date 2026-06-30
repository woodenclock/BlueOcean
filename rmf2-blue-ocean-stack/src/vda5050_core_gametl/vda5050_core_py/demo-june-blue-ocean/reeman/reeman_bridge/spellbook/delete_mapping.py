#!/usr/bin/env python3
"""DELETE /mappings/{id} — delete one mapping task."""

import sys

from api_client import request_api


def delete_mapping(mapping_id: int) -> bool:
    data = request_api("DELETE", f"/mappings/{int(mapping_id)}")
    return data is not None


if __name__ == "__main__":
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not arg.isdigit():
        print("Usage: delete_mapping <mapping_id>")
        raise SystemExit(1)
    mid = int(arg)
    c = input(f"Delete mapping task id={mid}? [y/N]: ").strip().lower()
    if c not in ("y", "yes"):
        print("Aborted.")
        raise SystemExit(1)
    if delete_mapping(mid):
        print(f"Deleted mapping id={mid}.")
    else:
        raise SystemExit(1)
