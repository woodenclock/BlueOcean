#!/usr/bin/env python3
"""Example VDA5050 master webserver (FastAPI + Swagger).

The FMS-side counterpart to ``example_autoxing_client.py``. It drives the bound
``VDA5050Master`` over MQTT:

    Browser --HTTP--> this server --VDA5050Master.assign_order--> MQTT
            --> vda5050 adapter (example_autoxing_client.py) --> AutoXing L300

Plan intake endpoint:

  POST /plans/mapf   accepts a planned route from the MAPF planner, re-resolves
                     coordinates against the master topology map and dispatches
                     it as a VDA5050 Order over MQTT.

This server only validates / assigns / delivers; it does not plan routes.

Run with uv (from this folder). fastapi/uvicorn are declared in the PEP 723
block below, so uv provisions an isolated env on first run. The vda5050_core_py
binding is a colcon-built C extension, so source the ROS workspace first to put
it on PYTHONPATH (uv inherits PYTHONPATH; --python 3.10 matches the binding's
ABI)::

    source /opt/ros/humble/setup.bash
    source ../../install/setup.bash         # exports vda5050_core_py on PYTHONPATH
    uv run --python 3.10 example_master_webserver.py
    # then open http://127.0.0.1:8000/docs

Prerequisites for orders to actually publish: a running MQTT broker (mosquitto)
and a ready AGV (example_autoxing_client.py + robot). assign_order runs a
readiness pre-flight (ONLINE + AUTOMATIC + position-initialized); without a live
AGV the endpoint returns AGV_OFFLINE / AGV_NO_STATE_YET rather than publishing.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fastapi>=0.110",
#     "uvicorn>=0.29",
#     "websockets>=12",
#     "rich>=13",
#     "pika>=1.3",
#     "pyyaml>=6",
# ]
# ///

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import struct
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from contextlib import asynccontextmanager

import pika
import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from rich.console import Console
from rich.pretty import pprint
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import vda5050_core_py as vda

# Diagnostics on stderr, default style red (not a property of sys.stderr itself).
stderr_console = Console(stderr=True, style="bold red")

# ===== Configuration (matches example_autoxing_client.py) =====
BROKER = os.environ.get("MQTT_BROKER", "tcp://localhost:1883")
CLIENT_ID = "example_master"
INTERFACE = "uagv"
PROTOCOL_VERSION = "2.0.0"

# Robot IP/URL config for direct jack control (set in config/config.env or real env file).
# AutoXing: full base URL e.g. http://192.168.68.64:8090
AUTOXING_BASE_URL = os.environ.get("AUTOXING_BASE_URL", "").rstrip("/")
# Reeman: host or host:port (no scheme)
REEMAN_ROBOT_IP = os.environ.get("REEMAN_ROBOT_IP", "")
# Real-demo master map id (AutoXing "From Mapping 40" frame). Override via VDA5050_MAP_ID.
# Used only as a fallback; the canonical layout's `map.id` is authoritative.
MAP_ID = os.environ.get("VDA5050_MAP_ID", "From Mapping 40")

# This master is the single map/transform/robots authority for the stack: it
# loads the canonical files from maps/ and serves them over HTTP (/map,
# /map/grid, /transform, /robots). In docker these are mounted at /app/maps and
# the paths below are set explicitly per compose profile; the defaults resolve
# the repo's maps/ dir for local (non-docker) runs from this folder.
_MAPS_DIR = Path(__file__).resolve().parents[4] / "maps"

# Canonical LIF layout (nodes + metric x/y + edges). The master validates/dispatches
# against the metric coords; the planner fetches the grid view via /map/grid.
MASTER_MAP_FILE = os.environ.get(
    "MASTER_MAP_FILE",
    str(_MAPS_DIR / MAP_ID / "real.layout.lif.json"),
)

# Canonical robot config (identity + onboard maps + per-mode routes).
MASTER_ROBOTS_FILE = os.environ.get("MASTER_ROBOTS_FILE", str(_MAPS_DIR / "robots.yaml"))

# Canonical frame transforms (served verbatim over /transform).
MAP_TF_FILE = os.environ.get("MAP_TF_FILE", str(_MAPS_DIR / "map_transforms.yaml"))

# Optional master-frame occupancy map image (PNG) + its ROS map_server metadata
# (resolution + origin), served to the UI over /map/image and /map/image/meta so
# the visualiser can drape the real building map behind the topology nodes (the
# layout coords share this image's AutoXing master frame).
MASTER_MAP_IMAGE_FILE = os.environ.get("MASTER_MAP_IMAGE_FILE")  # PNG to serve
MASTER_MAP_IMAGE_META = os.environ.get("MASTER_MAP_IMAGE_META")  # ROS yaml (res/origin)

# AMQP back-channel: when a robot's order completes (nodeStates emptied,
# §6.6.1), the master emits a TaskComplete on the @RECEIVE@ fanout so the MAPF
# planner can drop the finished task from its joint-plan batch. Best-effort —
# the master never blocks on the broker being reachable.
AMQP_HOST = os.environ.get("AMQP_HOST", "amqp-broker")
AMQP_PORT = int(os.environ.get("AMQP_PORT", "5672"))
AMQP_EXCHANGE = "@RECEIVE@"


def _resolve_path(path_str: str) -> Path:
    """Resolve a configured path: absolute as-is, else relative to this folder
    then to the repo maps/ dir (covers both docker and local runs)."""
    path = Path(path_str)
    if path.is_absolute():
        return path
    here = Path(__file__).parent / path
    return here if here.exists() else (_MAPS_DIR / path)


def _load_robots() -> list[dict]:
    """Canonical robot config from maps/robots.yaml (identity + routes)."""
    with _resolve_path(MASTER_ROBOTS_FILE).open() as f:
        return yaml.safe_load(f)["robots"]


def _load_layout() -> dict:
    """Parse the canonical LIF JSON into the structures the master serves.

    Returns metric ``nodes``/``edges`` in VDA5050-config shape (edges expanded
    bidirectionally so the C++ map loader and traversability validator behave
    exactly as with the old hand-written JSON), plus the undirected
    ``raw_edges`` / ``blocked_edges`` the planner's grid view needs.
    """
    map_path = _resolve_path(MASTER_MAP_FILE)
    # lif_loader.py lives in the maps/ root. Locally that's _MAPS_DIR; in docker
    # the maps tree is mounted elsewhere (e.g. /app/maps), so also try the dir
    # two levels up from the resolved map file (maps/<floor>/real.layout.lif.json).
    for cand in (_MAPS_DIR, map_path.parent.parent):
        if cand.exists() and str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
    from lif_loader import lif_to_layout  # noqa: PLC0415

    return lif_to_layout(json.loads(map_path.read_text()))


def _layout_to_config_json(layout: dict) -> dict:
    """Canonical layout -> the JSON document master.load_map_from_config expects."""
    return {
        "map_info": {
            "map_id": layout["map_id"],
            "map_version": layout["version"],
            "map_status": "ENABLED",
        },
        "nodes": layout["nodes"],
        "edges": layout["edges"],
    }


def _load_map_image() -> dict | None:
    """Resolve the optional master-frame map image + its ROS metadata.

    Returns ``{path, resolution, origin: [x, y, theta], width, height}`` (px
    width/height read straight from the PNG IHDR header — no image library) or
    ``None`` when no image is configured / files are missing. The UI overlays
    the PNG using resolution + origin to align it with the topology node coords.
    """
    if not MASTER_MAP_IMAGE_FILE or not MASTER_MAP_IMAGE_META:
        return None
    try:
        png = _resolve_path(MASTER_MAP_IMAGE_FILE)
        meta = yaml.safe_load(_resolve_path(MASTER_MAP_IMAGE_META).read_text())
        origin = [float(v) for v in meta["origin"]]
        with png.open("rb") as f:
            hdr = f.read(24)  # 8-byte signature + IHDR length/type + width/height
        width, height = struct.unpack(">II", hdr[16:24])
        return {
            "path": str(png),
            "resolution": float(meta["resolution"]),
            "origin": origin,
            "width": int(width),
            "height": int(height),
        }
    except (OSError, KeyError, ValueError, struct.error) as exc:
        print(f"Map image load failed ({MASTER_MAP_IMAGE_FILE}): {exc}", file=sys.stderr)
        return None


def _load_transform() -> dict:
    """Frame transforms (maps/map_transforms.yaml) as a JSON-able dict."""
    try:
        return yaml.safe_load(_resolve_path(MAP_TF_FILE).read_text()) or {}
    except OSError as exc:  # served best-effort; consumers handle empty
        print(f"Transform load failed ({MAP_TF_FILE}): {exc}", file=sys.stderr)
        return {}


ROBOTS = _load_robots()

# Single unified id: robots.yaml now carries one `robot_id` (was planner_id +
# fleet_id). Tolerate the old schema so a stale file still loads.
for _r in ROBOTS:
    _r["robot_id"] = _r.get("robot_id") or _r.get("planner_id") or _r.get("fleet_id")
    _r.setdefault("endpoint", "")

# Robot REST endpoints are now the per-robot `endpoint` field in robots.yaml
# (single source of truth); the env vars remain ad-hoc overrides for the AutoXing
# jack poller / ad-hoc overrides only.
def _endpoint_for(manufacturer: str) -> str:
    return next(
        (r.get("endpoint", "") for r in ROBOTS
         if r.get("manufacturer") == manufacturer and r.get("endpoint")),
        "",
    )


if not AUTOXING_BASE_URL:
    AUTOXING_BASE_URL = _endpoint_for("Autoxing").rstrip("/")
if not REEMAN_ROBOT_IP:
    REEMAN_ROBOT_IP = _endpoint_for("Reeman")

# AGVs onboarded at startup so their MQTT state is already tracked when the
# first MAPF plan arrives (onboarding only at plan time would race the
# adapter's next state publish and fail pre-flight with AGV_NO_STATE_YET).
ONBOARD_AGVS = [(r["manufacturer"], r["serial_number"]) for r in ROBOTS]

# ===== API models =====
class DepartureBlocker(BaseModel):
    """Hold rule: do not leave this waypoint until ``robot_id`` has progressed
    past ``required_progress`` along its own plan."""

    robot_id: str
    required_progress: float


class PlanWaypoint(BaseModel):
    name: str
    x: float
    y: float
    # CBS timestep of this waypoint in its robot's plan — the value other
    # robots' departure_blockers (required_progress) compare against. Falls
    # back to the waypoint index when the planner doesn't send it.
    progress: float | None = None
    departure_blockers: list[DepartureBlocker] = Field(default_factory=list)
    # VDA5050 node actions to execute when the robot reaches this waypoint.
    # Each dict: action_type (str), action_id (str, auto-generated if absent),
    # blocking_type ("HARD"|"SOFT"|"NONE", default "HARD"), action_description (str, optional).
    actions: list[dict] = Field(default_factory=list)


class MapfPlanRequest(BaseModel):
    """A planned route for one robot, as produced by the MAPF planner.

    Carries everything the master needs to later build and dispatch a VDA5050
    order: identity (robot / manufacturer / serial), the plan metadata, and the
    full waypoint list with positions and departure blockers.
    """

    robot_id: str
    manufacturer: str
    serial_number: str
    order_id: str
    map_id: str = "gametl_demo"
    plan_version: int = 0
    task_id: str = ""
    waypoints: list[PlanWaypoint]


class MapfPlanResponse(BaseModel):
    accepted: bool
    robot_id: str
    order_id: str
    waypoints: int
    blockers: int
    dispatched: bool
    decision: str
    errors: list[str] = Field(default_factory=list)
    note: str


class MapfPlanResetResponse(BaseModel):
    cleared_robots: list[str]
    pending_cancelled: int
    had_active_dispatch: bool


# ===== Master lifecycle =====
class _State:
    master: vda.VDA5050Master | None = None
    # Latest MAPF plan per robot_id, as received from the planner. Dispatched
    # as-is in planner-frame coordinates; the reeman adapter TFs its poses into
    # the AutoXing master frame (the reference) so real robots can follow these.
    mapf_plans: dict[str, MapfPlanRequest] = {}
    # Direct-navigate last_node_id override: robot_id -> {"node_id", "shadow"}.
    # direct-navigate bypasses VDA5050, so the order-driven last_node_id would
    # otherwise stay stale. This pins it to the snapped destination until the AGV
    # reports a last_node_id different from `shadow` (the value at override time),
    # i.e. until a real VDA5050 order advances the node. See POST /state/last-node.
    manual_last_node: dict[str, dict] = {}
    # Parsed topology map (nodes/edges), served to the visualiser over /ws/state.
    map_data: dict = {}
    # map_id of the loaded topology map and node lookup by node_id. Order
    # coordinates are re-resolved against these, so MASTER_MAP_FILE is the
    # single source of master-frame coords (the planner stays grid-frame).
    map_id: str = ""
    map_nodes: dict[str, dict] = {}
    # Planner grid view (undirected edges + blocked_edges), served over
    # /map/grid so the MAPF planner stops reading its own LIF file. Robot
    # positions come from live /state, not config.
    grid: dict = {}
    # Frame transforms (maps/map_transforms.yaml), served over /transform.
    transform: dict = {}
    # Optional master-frame map image + ROS metadata (resolution/origin/size),
    # served over /map/image + /map/image/meta. None when no image configured.
    map_image: dict | None = None
    # Last dispatched VDA5050 order per robot_id:
    # {"order_id", "update_id", "released_until"}. Lets a replan for a
    # mid-order robot go out as a stitched update (same order_id, bumped
    # update id) instead of a new order_id (which the stitch guard rejects
    # while an order is in flight), and tracks how far the order's base has
    # been released for departure-blocker enforcement.
    dispatched_orders: dict[str, dict] = {}


state = _State()

# Jack state cache — robot_id → "unknown"|"hold"|"jacking_up"|"jacking_down"|"up"|"down"|None.
# AutoXing reports live state via WS polling; Reeman is updated optimistically on command.
_jack_states: dict[str, str | None] = {}


async def _poll_jack_once(base_url: str) -> str | None:
    """Subscribe to a robot's WS /jack_state and return the first state value.

    AutoXing and Reeman share the ``/ws/v2/topics`` + ``enable_topic`` protocol
    (see each spellbook's jack_state command). The robot may send an
    ``enabled_topics`` ack and other topic payloads before ``/jack_state``;
    ``state`` is on the jack message top level."""
    if not base_url:
        return None
    host_port = base_url
    for prefix in ("http://", "https://", "ws://", "wss://"):
        if host_port.startswith(prefix):
            host_port = host_port[len(prefix):]
            break
    host_port = host_port.rstrip("/")
    ws_uri = f"ws://{host_port}/ws/v2/topics"
    try:
        import websockets as _ws
        async with _ws.connect(ws_uri, open_timeout=2) as ws:
            await ws.send(json.dumps({"enable_topic": "/jack_state"}))
            deadline = asyncio.get_event_loop().time() + 2.0
            while asyncio.get_event_loop().time() < deadline:
                remaining = max(0.1, deadline - asyncio.get_event_loop().time())
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                data = json.loads(raw)
                if data.get("topic") != "/jack_state":
                    continue
                st = data.get("state")
                if st is None:
                    payload = data.get("data", {})
                    if isinstance(payload, dict):
                        st = payload.get("state")
                return st if isinstance(st, str) else None
    except Exception:
        return None
    return None


async def _poll_and_store_jack(robot_id: str, base_url: str) -> None:
    """Poll one robot's jack state and cache it (best-effort — keep last on fail)."""
    try:
        st = await _poll_jack_once(base_url)
        if st is not None:
            _jack_states[robot_id] = st
    except Exception:  # noqa: BLE001 — best-effort polling
        pass


async def _jack_state_watcher() -> None:
    """Background task: poll AutoXing jack state every 1 s into _jack_states."""
    while True:
        await asyncio.sleep(1.0)
        await asyncio.gather(*[
            _poll_and_store_jack(r["robot_id"], (r.get("endpoint") or "").strip())
            for r in ROBOTS
            if r.get("manufacturer") == "Autoxing"
            and r.get("robot_id")
            and (r.get("endpoint") or "").strip()
        ])


def _robot_jack_post(url: str) -> dict:
    """HTTP POST to a robot jack endpoint; returns {"success": bool, ...}."""
    req = urllib.request.Request(
        url, data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"success": True, "raw": json.loads(body) if body.strip() else {}}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _robot_cmd_request(url: str, method: str = "POST", body: dict | None = None) -> dict:
    """HTTP request to a robot control endpoint (POST/PATCH/...); returns
    {"success": bool, ...}. Generalises _robot_jack_post for stop/cancel, which
    is a Reeman POST but an AutoXing PATCH with a JSON body."""
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return {"success": True, "raw": json.loads(raw) if raw.strip() else {}}
    except urllib.error.HTTPError as exc:
        return {"success": False, "status": exc.code, "message": str(exc)}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _cancel_robot_move(robot: dict) -> dict:
    """Cancel a robot's current move via its REST control plane (no MAPF/VDA5050).

    Idempotent: with nothing to cancel (the robot has no active move → 404) the
    stop has already achieved its goal, so we report success. Shared by the
    ``/actions/stop`` endpoint and the MAPF supersede path (a new Apply order
    overriding an in-flight one — see ``receive_mapf_plan``)."""
    rid = robot["robot_id"]
    mfg = robot["manufacturer"]
    endpoint = (robot.get("endpoint") or "").strip()
    if mfg == "Autoxing" and endpoint:
        url = f"{endpoint.rstrip('/')}/chassis/moves/current"
        result = _robot_cmd_request(url, method="PATCH", body={"state": "cancelled"})
    elif mfg == "Reeman" and endpoint:
        base = endpoint if endpoint.startswith("http") else f"http://{endpoint}"
        result = _robot_cmd_request(f"{base.rstrip('/')}/cmd/cancel_goal", method="POST")
    else:
        return {
            "robot_id": rid, "success": True,
            "note": f"No {mfg} endpoint configured — stop is a no-op.",
        }
    if not result.get("success") and result.get("status") == 404:
        result = {"success": True, "note": "No active move to cancel (already stopped)."}
    result["robot_id"] = rid
    return result


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Best-effort: the server still starts (and Swagger is demoable) even with
    # no broker — connect()/onboard just log failures.
    try:
        mqtt = vda.create_default_mqtt_client(BROKER, CLIENT_ID)
        master = vda.VDA5050Master.make(mqtt)
        master.connect()
        for manufacturer, serial in ONBOARD_AGVS:
            master.onboard_agv(manufacturer, serial)
        map_path = _resolve_path(MASTER_MAP_FILE)
        try:
            layout = _load_layout()
            # The C++ binding only loads from a JSON file path (no in-memory
            # variant is exposed), so feed it an ephemeral temp JSON expanded
            # from the canonical layout — nothing generated is committed.
            config_json = _layout_to_config_json(layout)
            tmp = tempfile.NamedTemporaryFile(
                "w", suffix=".json", prefix="vda5050_map_", delete=False
            )
            try:
                json.dump(config_json, tmp)
                tmp.close()
                ok, errs = master.load_map_from_config(tmp.name)
            finally:
                os.unlink(tmp.name)
            if not ok:
                stderr_console.print(f"Map load FAILED ({map_path}):")
                pprint(errs, console=stderr_console)
            state.map_data = {
                "nodes": layout["nodes"],
                "edges": layout["edges"],
                "stations": layout.get("stations", []),
            }
            state.map_id = layout["map_id"]
            state.map_nodes = {n["node_id"]: n for n in layout["nodes"]}
            # Robot positions come from live /state — no config starts in
            # /map/grid.
            state.grid = {
                "nodes": [n["node_id"] for n in layout["nodes"]],
                "edges": layout["raw_edges"],
                "blocked_edges": layout["blocked_edges"],
            }
            state.transform = _load_transform()
            state.map_image = _load_map_image()
        except Exception as exc:  # noqa: BLE001 — keep the server up regardless
            print(f"Canonical map load failed ({map_path}): {exc}", file=sys.stderr)
        state.master = master
        print(f"Master connected={master.is_connected()}, map {map_path.name}, "
              f"onboarded {ONBOARD_AGVS}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — keep the webserver up regardless
        print(f"Master startup failed (server still up): {exc}", file=sys.stderr)
    watcher = asyncio.create_task(_release_watcher())
    jack_watcher = asyncio.create_task(_jack_state_watcher())
    yield
    watcher.cancel()
    jack_watcher.cancel()
    if state.master is not None:
        try:
            state.master.disconnect()
        except Exception as exc:  # noqa: BLE001
            print(f"Master disconnect failed: {exc}", file=sys.stderr)


TAGS = [
    {"name": "2 · Status", "description": "Master / AGV observability."},
    {"name": "3 · MAPF Plans", "description": "Plan intake from the MAPF planner."},
    {"name": "4 · Jack Control", "description": "Direct jack up / down commands to robots."},
]

app = FastAPI(
    title="VDA5050 Example Master Webserver",
    description=__doc__,
    version="0.1.0",
    openapi_tags=TAGS,
    lifespan=lifespan,
)

# The UI (served from a different origin/port) fetches /map/image/meta directly
# from the master, which needs CORS. Permissive for this demo stack.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_master() -> vda.VDA5050Master:
    if state.master is None:
        raise HTTPException(503, "Master not initialized (startup failed).")
    return state.master


# ===== MAPF plan intake =====
def first_hold_index(req: MapfPlanRequest) -> int:
    """Index of the first waypoint with departure blockers (the first hold
    point), or the final index when the plan has none — i.e. how far the
    initial order's base may be released."""
    for i, waypoint in enumerate(req.waypoints):
        if waypoint.departure_blockers:
            return i
    return len(req.waypoints) - 1


def _plan_node_id(waypoint: PlanWaypoint) -> str:
    """The map node id a plan waypoint resolves to.

    Pickup/dropoff goal nodes — waypoints carrying node actions (the
    ``jackUp`` / ``jackDown`` that pick up or drop off the load) — are *snapped
    to the nearest topology node* instead of trusting the planner-supplied
    last-node id: a move-items goal that isn't itself a graph node (e.g. a rack
    / station point) still lands on a real map node, so the jack fires at the
    right place and the order passes the master's map-integrity validation.

    The snap uses the node's own master-frame coords when the name is already a
    known node (so it returns that same node — a frame-agnostic no-op that never
    relabels a valid goal), and only falls back to the planner coords for an
    off-graph goal name. Plain transit waypoints keep their id unchanged."""
    if not waypoint.actions:
        return waypoint.name
    node_def = state.map_nodes.get(waypoint.name)
    x = float(node_def["x"]) if node_def else waypoint.x
    y = float(node_def["y"]) if node_def else waypoint.y
    snapped = _snap_to_map_node(x, y)
    return snapped if snapped is not None else waypoint.name


def build_plan_order(
    req: MapfPlanRequest,
    order_id: str | None = None,
    order_update_id: int = 0,
    released_until: int | None = None,
    from_idx: int = 0,
    seq_base: int = 0,
) -> vda.Order:
    """MAPF plan waypoints[from_idx:] -> VDA5050 Order.

    Departure blockers are enforced via the VDA5050 base/horizon split:
    nodes/edges up to and including waypoint ``released_until`` are released
    (the base); everything after is the unreleased horizon the AGV must not
    enter. The release watcher later extends the base with stitched order
    updates (same order_id, bumped update id, ``from_idx`` = the hold
    waypoint) as blocking robots make progress. ``released_until=None``
    releases everything.

    ``seq_base`` offsets the VDA5050 sequence ids so they stay monotonic per
    order_id across stitched re-solves: waypoint ``i`` gets ``seq_base + 2*i``.
    A fresh order uses ``seq_base=0`` (the historical ``2*i`` numbering); a
    stitch sets it to the AGV's reported ``last_node_sequence_id`` so the
    robot's current node keeps the id it already reached and the adapter
    resumes after it instead of re-driving from the start.
    """
    nodes = []
    edges = []
    # Resolve every waypoint to its map node id up front so the snapped goal id
    # (pickup/dropoff nodes are snapped to the nearest topology node — see
    # _plan_node_id) is used consistently for the node AND the edge into it.
    node_ids = [_plan_node_id(w) for w in req.waypoints]
    for i in range(from_idx, len(req.waypoints)):
        waypoint = req.waypoints[i]
        node_id = node_ids[i]
        if node_id != waypoint.name:
            print(
                f"Snap goal {waypoint.name!r} -> nearest node {node_id!r} "
                f"(pickup/dropoff actions {[a.get('action_type') for a in waypoint.actions]})",
                file=sys.stderr,
            )
        released = released_until is None or i <= released_until
        # Re-resolve coordinates by the (possibly snapped) node id against the
        # loaded topology map: the planner sends grid-frame coords, the master's
        # map carries the master-frame ones. Planner coords are only a fallback
        # for waypoints missing from the map.
        node_def = state.map_nodes.get(node_id)
        # Position-only orders for now: x/y + optional XY tolerance. Leave
        # theta and allowed_deviation_theta unset (null) — do not default to 0.
        pos = vda.NodePosition()
        pos.x = float(node_def["x"]) if node_def else waypoint.x
        pos.y = float(node_def["y"]) if node_def else waypoint.y
        if node_def and "allowed_deviation_xy" in node_def:
            pos.allowed_deviation_x_y = float(node_def["allowed_deviation_xy"])
        pos.map_id = state.map_id or req.map_id
        node = vda.Node()
        node.node_id = node_id
        node.sequence_id = seq_base + 2 * i
        node.released = released
        node.node_position = pos
        if waypoint.actions:
            built_actions = []
            for a in waypoint.actions:
                act = vda.Action()
                act.action_type = a["action_type"]
                act.action_id = a.get("action_id") or str(uuid.uuid4())
                bt = a.get("blocking_type", "HARD").upper()
                act.blocking_type = (
                    vda.BlockingType.HARD if bt == "HARD"
                    else vda.BlockingType.SOFT if bt == "SOFT"
                    else vda.BlockingType.NONE
                )
                if "action_description" in a:
                    act.action_description = a["action_description"]
                built_actions.append(act)
            node.actions = built_actions
        nodes.append(node)
        if i > from_idx:
            prev_id = node_ids[i - 1]
            edge = vda.Edge()
            edge.edge_id = f"edge_{prev_id}_{node_id}"
            edge.sequence_id = seq_base + 2 * i - 1
            edge.start_node_id = prev_id
            edge.end_node_id = node_id
            edge.released = released
            edges.append(edge)

    order = vda.Order()
    order.order_id = order_id if order_id is not None else req.order_id
    order.order_update_id = order_update_id
    order.header.version = PROTOCOL_VERSION
    order.header.manufacturer = req.manufacturer
    order.header.serial_number = req.serial_number
    order.nodes = nodes
    order.edges = edges
    return order


def _resolve_order_identity(req: MapfPlanRequest) -> tuple[str, int, int]:
    """Pick the (order_id, order_update_id, seq_base) a new plan dispatches under.

    A new order_id while the robot's previous order is still in flight is
    rejected by the master's stitch guard (concurrent orders, §6.6 — FMS must
    cancel first, and cancelOrder is not implemented adapter-side). So when the
    robot has an in-flight order, reuse THAT order_id with a bumped
    order_update_id: the core treats the new plan as an order update (stitched
    override) instead of rejecting it. Crucially, the active order_id is read
    from the AGV's own last State (its reported orderId while nodeStates is
    non-empty), not just our local ``dispatched_orders`` bookkeeping — so a new
    Apply still overrides the running order after a ``/plans/mapf/reset`` wiped
    that bookkeeping, or after a master restart. Once the AGV reports the order
    complete (nodeStates emptied, §6.6.1), a fresh order_id is dispatched as a
    normal new assignment.

    ``seq_base`` keeps VDA5050 sequence ids monotonic per order_id: a stitch
    anchors the new plan at the AGV's reported ``last_node_sequence_id`` (so its
    waypoint[0] — the robot's current node, since the planner re-fetches live
    pose — keeps the id it already reached and the adapter resumes after it). A
    fresh assignment starts at 0.
    """
    prev = state.dispatched_orders.get(req.robot_id)
    prev_order_id = prev["order_id"] if prev else None
    prev_update_id = prev["update_id"] if prev else -1

    master = state.master
    agv = master.get_agv(req.manufacturer, req.serial_number) if master else None
    last = agv.get_last_state() if agv else None
    agv_order_active = (
        last is not None and bool(last.order_id) and len(last.node_states) > 0
    )

    if agv_order_active:
        # Override the order the robot is actually running. Bump strictly past
        # both the robot-reported update_id and our locally tracked one.
        base_update = (
            max(prev_update_id, last.order_update_id)
            if last.order_id == prev_order_id
            else last.order_update_id
        )
        return last.order_id, base_update + 1, last.last_node_sequence_id

    # Robot idle / order complete / no State yet — fresh assignment.
    return req.order_id, 0, 0


@app.post(
    "/plans/mapf",
    response_model=MapfPlanResponse,
    tags=["3 · MAPF Plans"],
    summary="Receive a MAPF plan for one robot and dispatch it as a VDA5050 Order",
    description=(
        "General plan intake from the MAPF planner: one robot's full route as "
        "waypoints (name, x, y) plus departure blockers (waits behind another "
        "robot's progress). The master stores the latest plan per robot, then "
        "builds a VDA5050 `Order` and dispatches it via `assign_order` over "
        "MQTT.\n\n"
        "Coordinates are still raw planner-frame (map unification / TF reeman "
        "-> autoxing frame is pending), and departure blockers are stored but "
        "not enforced in the order — acceptable for the current demo. "
        "With no live, ready AGV the readiness pre-flight yields "
        "`AGV_OFFLINE` / `AGV_NO_STATE_YET` (`dispatched: false`); the plan "
        "is still stored and the request still succeeds."
    ),
)
def receive_mapf_plan(req: MapfPlanRequest):
    # Detect a destination change before overwriting the stored plan: a new
    # Apply moves the robot to a different goal, whereas routine replans keep
    # the same goal and only re-route. Only the former should preempt the
    # robot's current move (see the supersede cancel below).
    prev_plan = state.mapf_plans.get(req.robot_id)
    new_goal = req.waypoints[-1].name if req.waypoints else None
    prev_goal = (
        prev_plan.waypoints[-1].name
        if prev_plan and prev_plan.waypoints
        else None
    )
    goal_changed = new_goal is not None and new_goal != prev_goal

    state.mapf_plans[req.robot_id] = req
    blockers = sum(len(w.departure_blockers) for w in req.waypoints)
    path = " -> ".join(w.name for w in req.waypoints)

    master = _require_master()
    if (req.manufacturer, req.serial_number) not in master.get_onboarded_agvs():
        master.onboard_agv(req.manufacturer, req.serial_number)
    order_id, order_update_id, seq_base = _resolve_order_identity(req)
    stitched = order_id != req.order_id
    released_until = first_hold_index(req)
    result = master.assign_order(
        req.manufacturer, req.serial_number,
        build_plan_order(
            req, order_id, order_update_id, released_until, seq_base=seq_base,
        ),
    )
    dispatched = bool(result)
    decision = result.decision.name
    errors = [e.error_type for e in result.errors]
    # A stitch-queued update is still pending delivery, so it claims its
    # update id — the next replan must bump past it, not reuse it.
    if dispatched or decision == "STITCH_QUEUED":
        state.dispatched_orders[req.robot_id] = {
            "order_id": order_id,
            "update_id": order_update_id,
            "released_until": released_until,
            "seq_base": seq_base,
        }

    # Supersede: a new Apply (different goal) that overrode an in-flight order
    # (stitched onto the active order_id). Preempt the robot's current move via
    # its REST control plane so it abandons the old path immediately and picks
    # up the override, instead of finishing the current leg first. Routine
    # same-goal replans are left untouched (no goal_changed → no preemption).
    if (dispatched or decision == "STITCH_QUEUED") and stitched and goal_changed:
        cfg = _robot_cfg(req.robot_id)
        if cfg is not None:
            cancel = _cancel_robot_move(cfg)
            print(
                f"Supersede {req.robot_id}: new goal {new_goal} overrides active "
                f"order {order_id}; cancel current move "
                f"→ {'OK' if cancel.get('success') else 'FAILED'}",
                file=sys.stderr,
            )

    print(
        f"MAPF plan v{req.plan_version} {req.order_id}: {req.robot_id} "
        f"({req.manufacturer}/{req.serial_number}) {path} "
        f"[{blockers} blocker(s)] — dispatched={dispatched} ({decision})"
        + (f" as update {order_update_id} of {order_id}" if stitched else ""),
        file=sys.stderr,
    )
    if not dispatched:
        note = f"Stored; dispatch refused by pre-flight: {decision}."
    elif stitched:
        note = (
            f"Robot mid-order: dispatched as update {order_update_id} of "
            f"active order {order_id} (stitch-guarded) instead of new order "
            f"{req.order_id}."
        )
    else:
        note = (
            "Dispatched over MQTT (planner-frame coords; TF reeman -> autoxing "
            "frame and blocker enforcement still pending)."
        )
    return MapfPlanResponse(
        accepted=True,
        robot_id=req.robot_id,
        order_id=order_id,
        waypoints=len(req.waypoints),
        blockers=blockers,
        dispatched=dispatched,
        decision=decision,
        errors=errors,
        note=note,
    )


@app.get(
    "/plans/mapf",
    tags=["3 · MAPF Plans"],
    summary="Latest stored MAPF plan per robot",
)
def list_mapf_plans():
    return {robot_id: plan.model_dump() for robot_id, plan in state.mapf_plans.items()}


@app.post(
    "/plans/mapf/reset",
    response_model=MapfPlanResetResponse,
    tags=["3 · MAPF Plans"],
    summary="Clear stored MAPF plans and dispatch bookkeeping",
    description=(
        "Drops all stored MAPF plans and per-robot dispatch records "
        "(``mapf_plans``, ``dispatched_orders``), and cancels each AGV's "
        "master-side outbound order queue. Does **not** send ``cancelOrder`` "
        "to adapters — in-flight robot motion may continue until the current "
        "order finishes or is stopped out-of-band."
    ),
)
def reset_mapf_plans():
    master = _require_master()
    cleared_robots = list(state.mapf_plans.keys())
    had_active_dispatch = bool(state.dispatched_orders)
    pending_cancelled = 0
    state.mapf_plans.clear()
    state.dispatched_orders.clear()
    for mfg, serial in master.get_onboarded_agvs():
        agv = master.get_agv(mfg, serial)
        if agv is None:
            continue
        pending_cancelled += agv.get_pending_order_count()
        agv.cancel_pending_orders()
    print(
        f"MAPF reset: cleared plans for {cleared_robots or '(none)'}, "
        f"cancelled {pending_cancelled} pending outbound order(s), "
        f"had_active_dispatch={had_active_dispatch}",
        file=sys.stderr,
    )
    return MapfPlanResetResponse(
        cleared_robots=cleared_robots,
        pending_cancelled=pending_cancelled,
        had_active_dispatch=had_active_dispatch,
    )


def _robot_cfg(robot_id: str) -> dict | None:
    return next((r for r in ROBOTS if r["robot_id"] == robot_id), None)


def _clear_mapf_state_for_robot(robot_id: str) -> tuple[int, bool]:
    """Clear stored plan/dispatch for one robot; cancel its pending orders."""
    master = _require_master()
    pending_cancelled = 0
    had_active_dispatch = (
        robot_id in state.dispatched_orders or robot_id in state.mapf_plans
    )
    plan = state.mapf_plans.pop(robot_id, None)
    state.dispatched_orders.pop(robot_id, None)
    cfg = _robot_cfg(robot_id)
    manufacturer = plan.manufacturer if plan else (cfg or {}).get("manufacturer")
    serial_number = plan.serial_number if plan else (cfg or {}).get("serial_number")
    if manufacturer and serial_number:
        agv = master.get_agv(manufacturer, serial_number)
        if agv is not None:
            pending_cancelled = agv.get_pending_order_count()
            agv.cancel_pending_orders()
    return pending_cancelled, had_active_dispatch


@app.post(
    "/plans/mapf/reset/{robot_id}",
    response_model=MapfPlanResetResponse,
    tags=["3 · MAPF Plans"],
    summary="Clear stored MAPF plan for one robot",
    description=(
        "Drops the stored MAPF plan and dispatch record for ``robot_id`` and "
        "cancels that AGV's master-side outbound order queue. Does **not** send "
        "``cancelOrder`` to adapters."
    ),
)
def reset_mapf_plan_for_robot(robot_id: str):
    pending_cancelled, had_active_dispatch = _clear_mapf_state_for_robot(robot_id)
    print(
        f"MAPF reset ({robot_id}): cancelled {pending_cancelled} pending "
        f"outbound order(s), had_active_dispatch={had_active_dispatch}",
        file=sys.stderr,
    )
    return MapfPlanResetResponse(
        cleared_robots=[robot_id],
        pending_cancelled=pending_cancelled,
        had_active_dispatch=had_active_dispatch,
    )


# ===== Departure-blocker enforcement (release watcher) =====
def _robot_progress(robot_id: str) -> float | None:
    """A robot's current progress along its own stored plan: the ``progress``
    of the plan waypoint matching its last reached node (None when it has no
    plan / no state / hasn't reached a plan node yet)."""
    plan = state.mapf_plans.get(robot_id)
    if plan is None or state.master is None:
        return None
    agv = state.master.get_agv(plan.manufacturer, plan.serial_number)
    last = agv.get_last_state() if agv else None
    if last is None or not last.last_node_id:
        return None
    progress = None
    for i, waypoint in enumerate(plan.waypoints):
        # Match against the resolved (possibly snapped) node id — that's what
        # the AGV reports as last_node_id for a snapped pickup/dropoff goal.
        if _plan_node_id(waypoint) == last.last_node_id:
            p = waypoint.progress if waypoint.progress is not None else float(i)
            progress = p if progress is None else max(progress, p)
    return progress


def _blockers_satisfied(blockers: list[DepartureBlocker]) -> bool:
    for blocker in blockers:
        progress = _robot_progress(blocker.robot_id)
        if progress is None or progress < blocker.required_progress:
            return False
    return True


def _advance_releases() -> None:
    """Extend each held order's released base once its hold waypoint's
    departure blockers are satisfied, via a stitched order update (same
    order_id, bumped update id, starting at the hold waypoint per §6.6.2)."""
    master = state.master
    if master is None:
        return
    for robot_id, rec in list(state.dispatched_orders.items()):
        plan = state.mapf_plans.get(robot_id)
        if plan is None:
            continue
        last_idx = len(plan.waypoints) - 1
        hold_idx = rec["released_until"]
        if hold_idx >= last_idx:
            continue  # fully released
        if not _blockers_satisfied(plan.waypoints[hold_idx].departure_blockers):
            continue
        next_hold = next(
            (
                i
                for i in range(hold_idx + 1, last_idx + 1)
                if plan.waypoints[i].departure_blockers
            ),
            last_idx,
        )
        update_id = rec["update_id"] + 1
        order = build_plan_order(
            plan, rec["order_id"], update_id,
            released_until=next_hold, from_idx=hold_idx,
            seq_base=rec.get("seq_base", 0),
        )
        queued = master.publish_order(plan.manufacturer, plan.serial_number, order)
        rec["update_id"] = update_id
        rec["released_until"] = next_hold
        print(
            f"Blockers at {plan.waypoints[hold_idx].name} cleared for "
            f"{robot_id}: released through {plan.waypoints[next_hold].name} "
            f"as update {update_id} of {rec['order_id']} (queued={queued})",
            file=sys.stderr,
        )


def _publish_task_complete(robot_id: str, task_id: str) -> None:
    """Emit a TaskComplete to the @RECEIVE@ fanout for the MAPF planner.

    Best-effort and self-contained (connect → publish → close), mirroring the
    scheduler's publisher: completions are infrequent, so a short-lived
    connection avoids holding a pika channel inside the asyncio event loop.
    """
    message = {"type": "TaskComplete", "robot_id": robot_id, "task_id": task_id}
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=AMQP_HOST,
                port=AMQP_PORT,
                # Bound the connect: this runs in the asyncio watcher loop, so a
                # hung broker must not stall the release watcher / /ws/state feed.
                socket_timeout=2.0,
                blocked_connection_timeout=2.0,
            )
        )
    except (pika.exceptions.AMQPError, OSError) as exc:
        print(
            f"TaskComplete for {robot_id} not sent (AMQP {AMQP_HOST}:{AMQP_PORT} "
            f"unreachable): {exc}",
            file=sys.stderr,
        )
        return
    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=AMQP_EXCHANGE, exchange_type="fanout", durable=True
        )
        channel.basic_publish(
            exchange=AMQP_EXCHANGE, routing_key="", body=json.dumps(message)
        )
        print(
            f"TaskComplete sent: {robot_id} task={task_id or '<none>'}",
            file=sys.stderr,
        )
    finally:
        connection.close()


def _emit_completions() -> None:
    """Emit one TaskComplete per robot whose dispatched order just finished.

    Completion mirrors the stitch guard's test (``_resolve_order_identity``):
    the AGV's last state reports the dispatched ``order_id`` with an empty
    ``node_states`` (§6.6.1). The dispatched-order record is popped on the
    transition so the signal fires exactly once; a later replan for the same
    robot creates a fresh record (and a fresh order_id).
    """
    master = state.master
    if master is None:
        return
    for robot_id, rec in list(state.dispatched_orders.items()):
        plan = state.mapf_plans.get(robot_id)
        if plan is None:
            continue
        agv = master.get_agv(plan.manufacturer, plan.serial_number)
        last = agv.get_last_state() if agv else None
        completed = (
            last is not None
            and last.order_id == rec["order_id"]
            and len(last.node_states) == 0
        )
        if not completed:
            continue
        state.dispatched_orders.pop(robot_id, None)
        _publish_task_complete(robot_id, plan.task_id)


async def _release_watcher() -> None:
    while True:
        await asyncio.sleep(0.3)
        try:
            _advance_releases()
            _emit_completions()
        except Exception as exc:  # noqa: BLE001 — keep the watcher alive
            print(f"Release watcher error: {exc}", file=sys.stderr)


# ===== Status =====
_ROBOT_IDS = {
    (r["manufacturer"], r["serial_number"]): r["robot_id"] for r in ROBOTS
}


def _jack_state_from_action_states(action_states) -> str | None:
    """Derive human-readable jack state from the most recent jack action state."""
    for s in reversed(list(action_states)):
        if s.action_type == "jackUp":
            if s.action_status.name in ("RUNNING", "INITIALIZING"):
                return "jacking_up"
            if s.action_status.name == "FINISHED":
                return "up"
        elif s.action_type == "jackDown":
            if s.action_status.name in ("RUNNING", "INITIALIZING"):
                return "jacking_down"
            if s.action_status.name == "FINISHED":
                return "down"
    return None


def _resolve_jack_state(
    robot_id: str,
    manufacturer: str,
    action_states,
) -> str | None:
    polled = _jack_states.get(robot_id)
    from_actions = _jack_state_from_action_states(action_states)

    # AutoXing: live WS poll is authoritative — passthrough hold/jacking_* as-is.
    if manufacturer == "Autoxing" and polled is not None:
        return polled

    return from_actions if from_actions is not None else polled


def _snap_to_map_node(x: float, y: float) -> str | None:
    """node_id of the nearest topology node to (x, y) in the master frame, or
    None when no map is loaded."""
    nodes = state.map_nodes
    if not nodes:
        return None
    return min(
        nodes.values(),
        key=lambda n: (float(n["x"]) - x) ** 2 + (float(n["y"]) - y) ** 2,
    )["node_id"]


def _effective_last_node(robot_id: str, reported: str | None) -> str | None:
    """``last_node_id`` with the direct-navigate override applied.

    The override (POST /state/last-node) wins until the AGV reports a
    last_node_id different from the one it had when the override was set — i.e.
    until a real VDA5050 order advances the node — at which point it is dropped."""
    ov = state.manual_last_node.get(robot_id)
    if ov is None:
        return reported
    if (reported or "") != ov["shadow"]:
        state.manual_last_node.pop(robot_id, None)
        return reported
    return ov["node_id"]


def _agv_state_snapshot() -> dict:
    """Live pose snapshot of every onboarded AGV, for /state and /ws/state."""
    master = _require_master()
    agvs = []
    for mfg, serial in master.get_onboarded_agvs():
        agv = master.get_agv(mfg, serial)
        last = agv.get_last_state() if agv else None
        pose = last.agv_position if last is not None else None
        has_pose = bool(pose is not None and pose.position_initialized)
        robot_id = _ROBOT_IDS.get((mfg, serial), f"{mfg}/{serial}")
        vda_action_states = list(last.action_states) if last is not None else []
        agvs.append({
            "robot_id": robot_id,
            "manufacturer": mfg,
            "serial_number": serial,
            "connection_status": agv.get_connection_status().name if agv else None,
            "last_node_id": _effective_last_node(
                robot_id, last.last_node_id if last is not None else None
            ),
            # Authoritative VDA5050 motion flag — the adapter sets it False once
            # the robot has stopped at the final node. Consumers (e.g. the
            # scheduler mission runner) gate "arrived & settled" actions like
            # jack on this so they don't fire while the robot is still moving.
            # None when we have no state yet (treat as "still moving").
            "driving": bool(last.driving) if last is not None else None,
            "x": pose.x if has_pose else None,
            "y": pose.y if has_pose else None,
            "theta": pose.theta if has_pose else None,
            "has_pose": has_pose,
            "action_states": [
                {
                    "action_id": s.action_id,
                    "action_type": s.action_type,
                    "action_status": s.action_status.name,
                    "result_description": s.result_description,
                }
                for s in vda_action_states
            ],
            "jack_state": _resolve_jack_state(robot_id, mfg, vda_action_states),
        })
    return {"type": "state", "agvs": agvs}


@app.get("/map", tags=["2 · Status"], summary="Loaded topology map (map_id, nodes, edges)")
def get_map():
    """The topology map the master validates and dispatches against. The
    scheduler's live (dry_run=false) path snaps robot poses to these nodes."""
    return {"map_id": state.map_id, **state.map_data}


@app.get(
    "/map/grid",
    tags=["2 · Status"],
    summary="Planner grid view (node ids, undirected edges, blocked_edges, starts)",
)
def get_map_grid():
    """The MAPF planner's topology view, derived from the same canonical layout
    as /map: undirected ``edges``, ``blocked_edges``, and the ``nodes`` id list.
    The planner derives its integer grid by parsing the "col,row" node ids."""
    return {"mode": "real", "map_id": state.map_id, **state.grid}


@app.get(
    "/map/image/meta",
    tags=["2 · Status"],
    summary="Master-frame map image metadata (resolution, origin, pixel size)",
)
def get_map_image_meta():
    """ROS map_server metadata for the occupancy image served at /map/image:
    ``resolution`` (m/px), ``origin`` ([x, y, theta] of the image's lower-left
    corner in the master frame) and pixel ``width``/``height``. The UI uses
    these to drape the PNG behind the topology so node coords land on the image.
    404 when no image is configured."""
    if not state.map_image:
        raise HTTPException(404, "no map image configured")
    return {
        "resolution": state.map_image["resolution"],
        "origin": state.map_image["origin"],
        "width": state.map_image["width"],
        "height": state.map_image["height"],
        "url": "/map/image",
    }


@app.get(
    "/map/image",
    tags=["2 · Status"],
    summary="Master-frame occupancy map image (PNG)",
)
def get_map_image():
    """The master-frame occupancy map as a PNG. 404 when no image configured."""
    if not state.map_image:
        raise HTTPException(404, "no map image configured")
    return FileResponse(state.map_image["path"], media_type="image/png")


@app.get(
    "/transform",
    tags=["2 · Status"],
    summary="Frame transforms (maps/map_transforms.yaml)",
)
def get_transform():
    """Per-adapter robot-frame -> master-frame similarity transforms. Consumed
    by the scheduler's direct-navigate path (and any frame-aware client)."""
    return state.transform


@app.get(
    "/robots",
    tags=["2 · Status"],
    summary="Canonical robot config (identity + per-mode routes)",
)
def get_robots():
    """Unified robot config for the stack: identity (robot_id / manufacturer /
    serial_number / onboard_map / endpoint), the full per-mode ``routes``,
    plus the active-mode ``route`` and ``home`` convenience slices.

    ``robot_id`` is the single id used everywhere (scheduler/MAPF/UI/MQTT-state);
    ``endpoint`` is the robot's direct REST base/host (single source of truth for
    direct-navigate + jack control)."""
    out = []
    for r in ROBOTS:
        routes = r.get("routes", {})
        entry = {
            "robot_id": r["robot_id"],
            "manufacturer": r["manufacturer"],
            "serial_number": r["serial_number"],
            "endpoint": r.get("endpoint", ""),
            "onboard_map": r.get("onboard_map", {}),
            "routes": routes,
            "route": routes.get("real", {}),
            # Real demo uses live pose, not a config home node.
            "home": None,
        }
        out.append(entry)
    return {"mode": "real", "robots": out}


@app.post(
    "/actions/jack/{robot_id}/{direction}",
    tags=["4 · Jack Control"],
    summary="Send jack up or down command to a robot",
    description=(
        "``robot_id`` is the unified robot id (e.g. ``autoxing-1``, ``reeman-2-blue``). "
        "``direction`` is ``up`` or ``down``. "
        "Calls the robot's REST API when an IP is configured; otherwise updates in-memory state "
        "only (no-op). AutoXing only: ``POST /services/jack_up|down``."
    ),
)
def jack_control(robot_id: str, direction: str):
    if direction not in ("up", "down"):
        raise HTTPException(400, f"direction must be 'up' or 'down', got {direction!r}")

    robot = next(
        (r for r in ROBOTS if r["robot_id"] == robot_id),
        None,
    )
    if robot is None:
        raise HTTPException(404, f"Robot {robot_id!r} not in robots.yaml")

    rid = robot["robot_id"]
    mfg = robot["manufacturer"]
    if mfg == "Reeman":
        raise HTTPException(
            501,
            "Jack control is not enabled for Reeman in this demo — use AutoXing only.",
        )
    # Per-robot endpoint (robots.yaml is the single source of truth), so multiple
    # robots of the same type hit their own host.
    endpoint = (robot.get("endpoint") or "").strip()

    result: dict = {"robot_id": rid, "direction": direction}

    if mfg == "Autoxing" and endpoint:
        url = f"{endpoint.rstrip('/')}/services/jack_{direction}"
        r = _robot_jack_post(url)
        result.update(r)
        if r.get("success"):
            _jack_states[rid] = "jacking_up" if direction == "up" else "jacking_down"
    else:
        _jack_states[rid] = "up" if direction == "up" else "down"
        result["success"] = True
        result["note"] = f"No {mfg} endpoint configured — state updated in memory only (no-op)."

    print(
        f"Jack {direction}: {rid} ({mfg}) → "
        f"{'OK' if result.get('success') else 'FAILED'} "
        f"state={_jack_states.get(rid)!r}",
        file=sys.stderr,
    )
    return result


@app.post(
    "/actions/stop/{robot_id}",
    tags=["4 · Jack Control"],
    summary="Stop / cancel a robot's active movement",
    description=(
        "Cancels the robot's current navigation by calling its REST API directly "
        "(no MAPF/VDA5050 — same path as direct-navigate/jack). ``robot_id`` is the "
        "unified robot id (e.g. ``autoxing-1``, ``reeman-2-blue``). "
        "AutoXing: ``PATCH /chassis/moves/current {state: cancelled}``. "
        "Reeman: ``POST /cmd/cancel_goal``. With no endpoint configured (no-op) "
        "it is a no-op success."
    ),
)
def stop_robot(robot_id: str):
    robot = next((r for r in ROBOTS if r["robot_id"] == robot_id), None)
    if robot is None:
        raise HTTPException(404, f"Robot {robot_id!r} not in robots.yaml")

    result = _cancel_robot_move(robot)
    print(
        f"Stop: {robot['robot_id']} ({robot['manufacturer']}) "
        f"→ {'OK' if result.get('success') else 'FAILED'}",
        file=sys.stderr,
    )
    return result


class InstantActionRequest(BaseModel):
    actions: list[dict]
    """Each dict: action_type (str, required), action_id (str, auto-generated if absent),
    blocking_type (str: HARD/SOFT/NONE, default HARD), action_description (str, optional)."""


@app.post(
    "/actions/instant/{robot_id}",
    tags=["4 · Jack Control"],
    summary="Send VDA5050 instant actions to a robot",
    description=(
        "Dispatches instant actions to the named robot via ``assign_instant_actions`` "
        "over MQTT. ``robot_id`` is the unified robot id (e.g. ``autoxing-1``). "
        "**Note**: the adapter's C++ instant-action subscription is not yet wired — "
        "actions are queued and published but won't be received by the adapter until "
        "that C++ support lands. Use node actions (``actions`` field on ``PlanWaypoint``) "
        "for orchestrated jack operations."
    ),
)
def send_instant_actions(robot_id: str, req: InstantActionRequest):
    master = _require_master()
    robot = next(
        (r for r in ROBOTS if r["robot_id"] == robot_id),
        None,
    )
    if robot is None:
        raise HTTPException(404, f"Robot {robot_id!r} not in robots.yaml")

    ia = vda.InstantActions()
    ia.header.manufacturer = robot["manufacturer"]
    ia.header.serial_number = robot["serial_number"]
    ia.header.version = PROTOCOL_VERSION

    built = []
    for a in req.actions:
        act = vda.Action()
        act.action_type = a["action_type"]
        act.action_id = a.get("action_id") or str(uuid.uuid4())
        bt = a.get("blocking_type", "HARD").upper()
        act.blocking_type = (
            vda.BlockingType.HARD if bt == "HARD"
            else vda.BlockingType.SOFT if bt == "SOFT"
            else vda.BlockingType.NONE
        )
        if "action_description" in a:
            act.action_description = a["action_description"]
        built.append(act)
    ia.actions = built

    result = master.assign_instant_actions(robot["manufacturer"], robot["serial_number"], ia)
    print(
        f"Instant actions → {robot_id}: decision={result.decision.name} "
        f"actions={[a.action_type for a in built]}",
        file=sys.stderr,
    )
    return {
        "robot_id": robot["robot_id"],
        "decision": result.decision.name,
        "success": bool(result),
        "errors": [e.error_type for e in result.errors],
        "actions": [{"action_type": a.action_type, "action_id": a.action_id} for a in built],
    }


@app.get("/state", tags=["2 · Status"], summary="Live AGV poses (x, y, theta)")
def live_state():
    return _agv_state_snapshot()


@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket):
    """Visualiser feed: one map message on connect, then live AGV poses.

    First message: ``{"type": "map", "nodes": [...], "edges": [...]}``.
    Then every ~300 ms: the /state snapshot (``{"type": "state", "agvs": […]}``).
    """
    await websocket.accept()
    try:
        await websocket.send_json({"type": "map", **state.map_data})
        while True:
            try:
                snapshot = _agv_state_snapshot()
            except HTTPException as exc:  # master not initialized
                snapshot = {"type": "error", "detail": exc.detail, "agvs": []}
            await websocket.send_json(snapshot)
            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        pass


@app.get("/status", tags=["2 · Status"], summary="Master and AGV state")
def status():
    master = _require_master()
    agvs = []
    for mfg, serial in master.get_onboarded_agvs():
        agv = master.get_agv(mfg, serial)
        last = agv.get_last_state() if agv else None
        pose = last.agv_position if last is not None else None
        rid = _ROBOT_IDS.get((mfg, serial), f"{mfg}/{serial}")
        agvs.append({
            "robot_id": rid,
            "manufacturer": mfg,
            "serial_number": serial,
            "connection_status": agv.get_connection_status().name if agv else None,
            "operational_state": agv.get_operational_state().name if agv else None,
            "last_node_id": _effective_last_node(
                rid, last.last_node_id if last is not None else None
            ),
            "has_pose": bool(pose is not None and pose.position_initialized),
            "pending_order_count": agv.get_pending_order_count() if agv else 0,
            "order_active": bool(last is not None and len(last.node_states) > 0),
        })
    return {"broker_connected": master.is_connected(), "agvs": agvs}


class LastNodeOverrideRequest(BaseModel):
    """Pin a robot's last_node_id to a map node: ``node_id`` directly, or
    master-frame ``x``/``y`` (snapped to the nearest node)."""

    node_id: str | None = None
    x: float | None = None
    y: float | None = None


@app.post(
    "/state/last-node/{robot_id}",
    tags=["2 · Status"],
    summary="Override a robot's last_node_id (e.g. after direct-navigate)",
    description=(
        "Pins ``robot_id``'s reported ``last_node_id`` to a map node. "
        "direct-navigate bypasses VDA5050, so the order-driven last_node_id "
        "would otherwise stay stale and the scheduler/MAPF planner would plan "
        "from the wrong node. The override is shadowed against the AGV's current "
        "last_node_id and dropped automatically once a real VDA5050 order "
        "advances the node. Provide ``node_id``, or master-frame ``x``/``y``."
    ),
)
def set_last_node(robot_id: str, req: LastNodeOverrideRequest):
    cfg = _robot_cfg(robot_id)
    if cfg is None:
        raise HTTPException(404, f"Robot {robot_id!r} not in robots.yaml")
    if req.node_id is not None:
        if req.node_id not in state.map_nodes:
            raise HTTPException(
                404, f"node_id {req.node_id!r} is not on the master map."
            )
        node = req.node_id
    elif req.x is not None and req.y is not None:
        node = _snap_to_map_node(req.x, req.y)
        if node is None:
            raise HTTPException(502, "No master map loaded; cannot snap pose.")
    else:
        raise HTTPException(422, "Provide node_id, or x and y.")

    master = _require_master()
    agv = master.get_agv(cfg["manufacturer"], cfg["serial_number"])
    last = agv.get_last_state() if agv else None
    shadow = last.last_node_id if last is not None else ""
    state.manual_last_node[robot_id] = {"node_id": node, "shadow": shadow}
    print(
        f"last_node override: {robot_id} → {node} (shadowing {shadow!r})",
        file=sys.stderr,
    )
    return {"robot_id": robot_id, "last_node_id": node, "shadowing": shadow}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


class _StatePollAccessLogFilter(logging.Filter):
    """Drop uvicorn access-log lines for high-frequency GET /state polls."""

    def filter(self, record: logging.LogRecord) -> bool:
        return 'GET /state ' not in record.getMessage()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--disable-state-log",
        action="store_true",
        help="Suppress uvicorn access logs for GET /state poll spam.",
    )
    args = parser.parse_args()
    port = int(os.environ.get("VDA5050_PORT", "8000"))
    if args.disable_state_log:
        logging.getLogger("uvicorn.access").addFilter(_StatePollAccessLogFilter())
    uvicorn.run(app, host="0.0.0.0", port=port)
