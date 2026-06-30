"""Resolve the adapter's identity, active map, and robot host from the master."""

from __future__ import annotations

import json
import os
import sys
import urllib.error

from adapter_core.config import MASTER_URL
from adapter_core.master_client import master_get


def bootstrap_identity(config: dict) -> dict:
    """Resolve this adapter's identity from the master /robots keyed by robot_id.

    The only per-adapter local config is ``ROBOT_ID`` (falls back to the
    container hostname) + ``MASTER_URL``. manufacturer / serial_number are taken
    from this robot's /robots entry and client_id is derived from them, so a
    second robot of the same make (e.g. reeman-2-blue) needs no own VDA5050_SERIAL.
    Explicit VDA5050_* env still wins; if the master can't be reached the CONFIG
    defaults stand. Mutates ``config`` in place; returns the /robots entry (or {}).
    """
    robot_id = config["robot_id"]
    try:
        robots = master_get("/robots")["robots"]
        me = next(r for r in robots if r.get("robot_id") == robot_id)
    except (
        urllib.error.URLError, OSError, ValueError, KeyError, StopIteration,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"[identity] master /robots lookup by robot_id={robot_id!r} failed: "
            f"{exc}; falling back to env/defaults "
            f"{config['manufacturer']}/{config['serial_number']}",
            file=sys.stderr,
        )
        return {}
    if not os.environ.get("VDA5050_MANUFACTURER"):
        config["manufacturer"] = me.get("manufacturer") or config["manufacturer"]
    if not os.environ.get("VDA5050_SERIAL"):
        config["serial_number"] = me.get("serial_number") or config["serial_number"]
    if not os.environ.get("VDA5050_CLIENT_ID"):
        config["client_id"] = (
            f"{config['manufacturer'].lower()}_{config['serial_number'].lower()}_agv"
        )
    return me


def resolve_map_id(config: dict) -> None:
    """Set ``config['map_id']`` to the master's active map (VDA5050_MAP_ID wins)."""
    if os.environ.get("VDA5050_MAP_ID"):
        return
    try:
        config["map_id"] = master_get("/map").get("map_id") or config["map_id"]
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(
            f"[map_id] master fetch failed; using {config['map_id']!r}: {exc}",
            file=sys.stderr,
        )


def export_endpoint(me: dict, config: dict, *, env_var: str, fallback_desc: str) -> None:
    """Publish this robot's ``endpoint`` (robots.yaml via the master /robots — the
    single source of truth) into ``env_var`` so the bridge drives the right host.
    An explicit env still wins."""
    if os.environ.get(env_var):
        return
    endpoint = (me.get("endpoint") or "").strip()
    if endpoint:
        os.environ[env_var] = endpoint
        print(f"[endpoint] {env_var} <- robots.yaml {endpoint!r}", file=sys.stderr)
    else:
        print(
            f"[endpoint] WARNING: no `endpoint` for {config['manufacturer']}/"
            f"{config['serial_number']} in the master /robots — {fallback_desc} "
            "Set this robot's endpoint in maps/robots.yaml.",
            file=sys.stderr,
        )
