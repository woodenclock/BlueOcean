"""Startup diagnostic: log the active map and flag a stale Reeman calibration."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def log_master_map_and_check_calibration() -> None:
    """Log the active (master) map and flag a stale Reeman calibration.

    The Reeman adapter calibrates against this robot's map (uid/map_version
    recorded in the calibration cache at MAP_TF_CACHE_PATH). If the master map
    was rebuilt since, the cached Reeman→AutoXing transform is stale and must be
    recomputed. Best-effort: never blocks this adapter.
    """
    try:
        # Autoxing spellbook is on sys.path once autoxing_bridge imported.
        from get_current_map import get_current_map  # noqa: PLC0415

        current = get_current_map()
        print(f"Active master map: {current}", file=sys.stderr)
        if not isinstance(current, dict):
            return

        cache_path = Path(
            os.environ.get(
                "MAP_TF_CACHE_PATH",
                Path.home() / ".cache" / "gametl" / "reeman_to_autoxing_tf.json",
            )
        )
        if not cache_path.is_file():
            return
        cached = json.loads(cache_path.read_text()).get("autoxing_map", {})
        for key in ("uid", "map_version"):
            if cached.get(key) is not None and cached.get(key) != current.get(key):
                print(
                    f"WARNING: master map {key} changed since the Reeman "
                    f"calibration (cached={cached.get(key)!r}, "
                    f"current={current.get(key)!r}) — the cached "
                    f"Reeman→AutoXing transform is stale; recalibrate with "
                    f"AutoXing online (python -m map_transform).",
                    file=sys.stderr,
                )
    except Exception as exc:  # noqa: BLE001 — diagnostic only
        print(f"Master map check skipped: {exc}", file=sys.stderr)
