#!/usr/bin/env python3
"""DELETE /maps/ — delete all maps on the robot."""

from api_client import request_api


def delete_all_maps() -> bool:
    data = request_api("DELETE", "/maps/", timeout=60)
    return data is not None


if __name__ == "__main__":
    c = input("Delete ALL maps on this robot? [y/N]: ").strip().lower()
    if c not in ("y", "yes"):
        print("Aborted.")
        raise SystemExit(1)
    if delete_all_maps():
        print("All maps deleted.")
    else:
        raise SystemExit(1)
