# Copyright 2024-2026 ROS Industrial Consortium Asia Pacific
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Rack nodes and their graph approach nodes, driven by the active VDA5050 map."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request

# Per-map static defaults (rack_node -> approach_node). Approach is the single
# connected neighbor — all rack nodes are dead-ends in both supported maps.
_RACK_NODES_BY_MAP: dict[str, dict[str, str | None]] = {
    "AMAV-X": {
        "3,4": "4,4",    # Rack_1
        "5,4": "4,4",    # Rack_2
        "6,6": "5,6",    # Rack_3
    },
    "l1-artc": {
        "3,4": "3,5",    # Rack_South
        "2,5": "3,5",    # Rack_West
        "4,6": "3,6",    # Rack_East
        "3,10": "3,9",   # HumanZone_Arm
        "4,10": "4,9",   # Rack_FarNorth
    },
}

MASTER_URL = os.environ.get("MASTER_URL", "http://localhost:8000").rstrip("/")
_MAP_ID = os.environ.get("VDA5050_MAP_ID", "AMAV-X")

# Rack node -> approach node ("the node before"). Node ids contain commas, so
# the env override uses ';' between entries and '=' between rack and approach, e.g.
#   RACK_NODES="3,4=4,4;5,4=4,4;6,6=5,6"
def _parse_rack_env(raw: str) -> dict[str, str | None]:
    racks: dict[str, str | None] = {}
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            rack, approach = item.split("=", 1)
            racks[rack.strip()] = approach.strip() or None
        else:
            racks[item] = None
    return racks


_rack_env = os.environ.get("RACK_NODES")
_DEFAULT_RACK_NODES: dict[str, str | None] = (
    _parse_rack_env(_rack_env)
    if _rack_env
    else dict(_RACK_NODES_BY_MAP.get(_MAP_ID, _RACK_NODES_BY_MAP["AMAV-X"]))
)
RACK_NODES: dict[str, str | None] = _DEFAULT_RACK_NODES

# Live cache: racks derived from the master /map stations. TTL-cached so rack
# changes (e.g. VDA5050_MAP_ID switch) propagate within one cycle.
_cache: dict[str, str | None] | None = None
_cache_time: float = 0.0
_cache_lock = threading.Lock()
_CACHE_TTL = 60.0


def _derive_from_master() -> dict[str, str | None] | None:
    """Fetch /map from master, extract Rack_* stations, derive approach nodes."""
    try:
        with urllib.request.urlopen(f"{MASTER_URL}/map", timeout=2) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None

    stations = data.get("stations", [])
    if not stations:
        return None

    neighbors: dict[str, list[str]] = {}
    for e in data.get("edges", []):
        s, t = e.get("start_node_id", ""), e.get("end_node_id", "")
        if s and t:
            neighbors.setdefault(s, []).append(t)

    rack_node_ids: set[str] = {
        n
        for st in stations
        if str(st.get("station_name", "")).startswith("Rack_")
        for n in st.get("node_ids", [])
    }

    result: dict[str, str | None] = {}
    for st in stations:
        if not str(st.get("station_name", "")).startswith("Rack_"):
            continue
        for node_id in st.get("node_ids", []):
            approach = next(
                (n for n in neighbors.get(node_id, []) if n not in rack_node_ids),
                None,
            )
            result[node_id] = approach

    return result or None


def get_rack_nodes() -> dict[str, str | None]:
    """Current rack map: tries live master, falls back to static defaults."""
    if _rack_env:
        return RACK_NODES

    global _cache, _cache_time
    now = time.monotonic()
    with _cache_lock:
        if _cache is not None and (now - _cache_time) < _CACHE_TTL:
            return _cache

    fresh = _derive_from_master()
    with _cache_lock:
        if fresh is not None:
            _cache = fresh
            _cache_time = now
            return fresh
        if _cache is not None:
            return _cache

    return RACK_NODES


def logical_graph_node(node_id: str | None) -> str | None:
    """After rack pick/drop the robot leaves from the approach node, not the rack."""
    if node_id is None:
        return None
    racks = get_rack_nodes()
    approach = racks.get(node_id)
    return approach if approach else node_id


def rack_departure_node(rack_node: str) -> str:
    """Graph node to use as the start of the next MAPF leg after a rack visit."""
    return logical_graph_node(rack_node) or rack_node
