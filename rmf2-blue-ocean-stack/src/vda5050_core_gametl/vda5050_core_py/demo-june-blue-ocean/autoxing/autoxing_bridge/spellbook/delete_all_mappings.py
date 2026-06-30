#!/usr/bin/env python3
"""DELETE /mappings/ — delete all mapping tasks."""

import sys

from api_client import request_api


def delete_all_mappings() -> bool:
    data = request_api("DELETE", "/mappings/")
    return data is not None


if __name__ == "__main__":
    c = input("Delete ALL mapping tasks on this robot? [y/N]: ").strip().lower()
    if c not in ("y", "yes"):
        print("Aborted.")
        raise SystemExit(1)
    if delete_all_mappings():
        print("All mapping tasks deleted.")
    else:
        raise SystemExit(1)
