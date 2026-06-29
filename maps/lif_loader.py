"""Load VDA5050 LIF JSON into the internal layout dict the master serves."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DEVIATION_XY = 0.25


def lif_to_layout(data: dict[str, Any], *, default_deviation: float = DEFAULT_DEVIATION_XY) -> dict:
    """Parse LIF JSON into master/planner layout shape (nodes, edges, grid)."""
    layouts = data.get("layouts")
    if not layouts:
        raise ValueError("LIF file missing layouts[]")

    lay = layouts[0]
    map_id = str(lay.get("layoutId", "map"))
    version = str(lay.get("layoutVersion", "1.0"))

    nodes: list[dict] = []
    for spec in lay.get("nodes", []):
        pos = spec["nodePosition"]
        node: dict[str, Any] = {
            "node_id": str(spec["nodeId"]),
            "x": float(pos["x"]),
            "y": float(pos["y"]),
            "allowed_deviation_xy": default_deviation,
        }
        nodes.append(node)

    raw_edges: list[list[str]] = []
    edges: list[dict] = []
    for spec in lay.get("edges", []):
        start_id = str(spec["startNodeId"])
        end_id = str(spec["endNodeId"])
        raw_edges.append([start_id, end_id])
        edges.append(
            {"edge_id": f"edge_{start_id}_{end_id}", "start_node_id": start_id, "end_node_id": end_id}
        )
        edges.append(
            {"edge_id": f"edge_{end_id}_{start_id}", "start_node_id": end_id, "end_node_id": start_id}
        )

    stations: list[dict] = []
    for s in lay.get("stations", []):
        pos = s.get("stationPosition", {})
        stations.append({
            "station_id": s["stationId"],
            "station_name": s["stationName"],
            "node_ids": s.get("interactionNodeIds", []),
            "x": float(pos.get("x", 0.0)),
            "y": float(pos.get("y", 0.0)),
        })

    return {
        "map_id": map_id,
        "version": version,
        "nodes": nodes,
        "edges": edges,
        "raw_edges": raw_edges,
        "blocked_edges": [],
        "stations": stations,
    }


def load_lif_file(path: str | Path) -> dict:
    """Load a LIF JSON file from disk."""
    return lif_to_layout(json.loads(Path(path).read_text()))
