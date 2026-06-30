"""Ensure each real adapter activates its demo onboard map at startup.

The onboard map id/name is the canonical ``onboard_map`` from the VDA5050
master's ``/robots`` (maps/robots.yaml), matched by manufacturer/serial — the
single source of truth. The env vars below still override if explicitly set
(handy for one-off bring-up), and there is a last-resort hardcoded fallback if
the master is unreachable:
  AUTOXING_ONBOARD_MAP_ID / AUTOXING_ONBOARD_MAP_NAME
  REEMAN_ONBOARD_MAP_NAME
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

MASTER_URL = os.environ.get("MASTER_URL", "http://vda5050:8000").rstrip("/")


def _log(msg: str) -> None:
    print(f"[onboard-map] {msg}", file=sys.stderr)


def _onboard_map_from_master(manufacturer: str, serial: str) -> dict[str, Any]:
    """This robot's ``onboard_map`` from the master /robots ({} on failure)."""
    try:
        with urllib.request.urlopen(f"{MASTER_URL}/robots", timeout=10) as resp:
            robots = json.loads(resp.read())["robots"]
        me = next(
            r for r in robots
            if r.get("manufacturer") == manufacturer
            and r.get("serial_number") == serial
        )
        return me.get("onboard_map", {}) or {}
    except (
        urllib.error.URLError, OSError, ValueError, KeyError, StopIteration,
    ) as exc:
        _log(f"could not fetch onboard_map from {MASTER_URL}/robots: {exc}")
        return {}


def _maps_match(current: dict[str, Any], *, map_id: int | None, map_name: str) -> bool:
    cur_id = current.get("id")
    if map_id is not None and cur_id is not None:
        try:
            if int(cur_id) == int(map_id):
                return True
        except (TypeError, ValueError):
            pass
    for key in ("map_name", "name", "alias", "map_uid", "uid"):
        val = current.get(key)
        if val is not None and str(val) == map_name:
            return True
    return False


def ensure_autoxing_onboard_map(
    manufacturer: str = "Autoxing", serial: str = "A001"
) -> dict[str, Any] | None:
    """Switch AutoXing to the demo map when a different map is active.

    Map id/name come from the master /robots onboard_map (env overrides win)."""
    from get_current_map import get_current_map  # noqa: PLC0415
    from switch_map import switch_map_by_numeric_id  # noqa: PLC0415

    om = _onboard_map_from_master(manufacturer, serial)
    map_id = int(os.environ.get("AUTOXING_ONBOARD_MAP_ID", om.get("id", 27)))
    map_name = os.environ.get("AUTOXING_ONBOARD_MAP_NAME", om.get("name", "From Mapping 40"))

    current = get_current_map()
    if isinstance(current, dict) and _maps_match(
        current, map_id=map_id, map_name=map_name
    ):
        _log(
            f"AutoXing already on demo map "
            f"(id={current.get('id')!r}, name={current.get('map_name')!r})"
        )
        return current

    if current:
        _log(
            f"AutoXing active map is id={current.get('id')!r} "
            f"name={current.get('map_name')!r}; switching to id={map_id} "
            f"({map_name!r})"
        )
    else:
        _log(f"AutoXing current map unknown; switching to id={map_id} ({map_name!r})")

    result = switch_map_by_numeric_id(map_id)
    if result is None:
        _log(f"WARNING: failed to switch AutoXing to map id={map_id}")
        return current if isinstance(current, dict) else None

    refreshed = get_current_map()
    if isinstance(refreshed, dict):
        _log(
            f"AutoXing now on id={refreshed.get('id')!r} "
            f"name={refreshed.get('map_name')!r}"
        )
        return refreshed
    return result if isinstance(result, dict) else None


def ensure_reeman_onboard_map(
    manufacturer: str = "Reeman", serial: str = "R001"
) -> dict[str, Any] | None:
    """Switch Reeman to the demo map when a different map is active.

    Map name comes from the master /robots onboard_map (env override wins)."""
    from get_current_map import get_current_map  # noqa: PLC0415
    from switch_map import switch_map_by_name  # noqa: PLC0415

    om = _onboard_map_from_master(manufacturer, serial)
    map_name = os.environ.get(
        "REEMAN_ONBOARD_MAP_NAME", om.get("name", "886d396851aa60b150419998b0a56e59")
    )

    current = get_current_map()
    if isinstance(current, dict) and _maps_match(
        current, map_id=None, map_name=map_name
    ):
        _log(
            f"Reeman already on demo map "
            f"(name={current.get('name') or current.get('map_name')!r})"
        )
        return current

    if current:
        _log(
            f"Reeman active map is "
            f"{current.get('name') or current.get('map_name') or current.get('alias')!r}; "
            f"switching to {map_name!r}"
        )
    else:
        _log(f"Reeman current map unknown; switching to {map_name!r}")

    result = switch_map_by_name(map_name)
    if result is None:
        _log(f"WARNING: failed to switch Reeman to map {map_name!r}")
        return current if isinstance(current, dict) else None

    refreshed = get_current_map()
    if isinstance(refreshed, dict):
        _log(
            f"Reeman now on "
            f"{refreshed.get('name') or refreshed.get('map_name')!r}"
        )
        return refreshed
    return result if isinstance(result, dict) else None
