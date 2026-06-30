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

"""Blue Ocean demo: publish two-robot GoTo Schedule messages to the task orchestrator.

One POST builds a crossflow ``Schedule`` envelope per robot and publishes each to
the AMQP ``@RECEIVE@`` fanout exchange, where the rmf2 task orchestrator runs
them as independent ``GoToNode`` workflows.
"""

import json
import math
import os
from functools import lru_cache
import urllib.error
import urllib.request
from uuid import uuid4

import pika
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/demo", tags=["Demo"])

AMQP_EXCHANGE = "@RECEIVE@"

# Robot config now comes from the VDA5050 master (GET /robots), the single
# source of truth — no more blue_ocean_robots.json. The master serves the
# canonical maps/robots.yaml; we map its schema (one unified robot_id +
# optional routes.{dry_run,real}) to this module's shape (robot_id /
# master_id [== robot_id] / dry_run / real).
#
# Navigation no longer requires configured start/goal positions: the goal is
# supplied per request (goal_node or x/y) and live mode (dry_run=false) resolves
# the start from the robot's /state pose snapped to the nearest /map node. The
# ``routes`` block is therefore optional — only the legacy two-robot crossflow
# (get_robot_locations) and dry-run starts read it, and they fail with a clear
# error only when that data is actually needed.


def load_robot_config() -> list[dict]:
    """Fetch robot config from the master /robots and map it to the scheduler's
    (robot_id, master_id, dry_run, real) shape.

    Only ``robot_id`` is required. ``routes`` is optional (``dry_run``/``real``
    default to ``{}``) so robots configured purely for request-driven navigation
    — goal from the request, start from live localization — need no start/goal."""
    data = _master_get("/robots")
    robots = [
        {
            # One unified id (the master now emits `robot_id`). master_id is kept
            # as an alias == robot_id because the master /state also reports poses
            # under robot_id; downstream lookups stay working.
            "robot_id": r.get("robot_id") or r.get("planner_id"),
            "master_id": r.get("robot_id") or r.get("fleet_id"),
            "manufacturer": r.get("manufacturer"),
            "serial_number": r.get("serial_number"),
            "endpoint": r.get("endpoint", ""),
            "dry_run": r.get("routes", {}).get("dry_run", {}),
            "real": r.get("routes", {}).get("real", {}),
        }
        for r in data.get("robots", [])
    ]
    bad = [r.get("robot_id", "?") for r in robots if not r.get("robot_id")]
    if bad:
        raise HTTPException(
            status_code=500,
            detail=f"Master /robots: entries {bad} need a robot_id.",
        )
    return robots


def _require_route(robot: dict, mode: str, key: str) -> str:
    """A configured route value (e.g. dry_run.start), or a clear 422 if absent.

    ``routes`` is optional in robots.yaml; this is only reached by flows that
    genuinely need a configured start/goal (the dry-run two-robot crossflow and
    dry-run mission starts). Request-driven navigation never calls it."""
    value = robot.get(mode, {}).get(key)
    if not value:
        raise HTTPException(
            status_code=422,
            detail=f"Robot {robot.get('robot_id', '?')!r} has no routes.{mode}.{key} "
            f"in robots.yaml — add it, or use request-driven navigation "
            "(goal from the request, start from live localization).",
        )
    return value


@lru_cache(maxsize=1)
def _safe_robot_config() -> list[dict]:
    """Best-effort ``load_robot_config`` for the import-time Swagger builders.

    The live endpoints keep the strict ``load_robot_config`` (which raises 500
    on a bad config); the OpenAPI examples/description are documentation, so an
    unreadable config must never crash app startup — fall back to an empty list.

    Cached: this is only used by the import-time Swagger example/description
    builders, which call it from three places — memoizing collapses three
    blocking ``/robots`` fetches into one.
    """
    try:
        return load_robot_config()
    except HTTPException:
        return []


class RobotSchedule(BaseModel):
    robot_id: str
    start: str
    goal: str
    task_id: str
    schedule_id: str
    schedule: dict


class BlueOceanResponse(BaseModel):
    dry_run: bool
    broker: str
    exchange: str
    robots: list[RobotSchedule]


def _master_get(path: str) -> dict:
    master_url = os.environ.get("MASTER_URL", "http://vda5050:8000")
    url = f"{master_url.rstrip('/')}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach VDA5050 master at {url}: {exc}",
        ) from exc


def snap_to_node(x: float, y: float, nodes: list[dict]) -> str:
    """Nearest topology node to (x, y), guarded by SNAP_MAX_DIST_M."""
    from demo_routes.racks import logical_graph_node

    max_dist = float(os.environ.get("SNAP_MAX_DIST_M", "3.0"))
    node = min(nodes, key=lambda n: (n["x"] - x) ** 2 + (n["y"] - y) ** 2)
    dist = math.hypot(node["x"] - x, node["y"] - y)
    if dist > max_dist:
        raise HTTPException(
            status_code=409,
            detail=f"Robot pose ({x:.2f},{y:.2f}) is {dist:.2f} m from the "
            f"nearest map node {node['node_id']} (limit {max_dist} m) — "
            "check robot localization and the map's real coordinates.",
        )
    return logical_graph_node(node["node_id"]) or node["node_id"]


def _master_nodes() -> list[dict]:
    nodes = _master_get("/map").get("nodes", [])
    if not nodes:
        raise HTTPException(
            status_code=502, detail="VDA5050 master returned an empty /map."
        )
    return nodes


def resolve_live_start(master_id: str, nodes: list[dict]) -> str:
    """The robot's live pose from the master's /state, snapped to a map node."""
    from demo_routes.racks import logical_graph_node

    agvs = {a.get("robot_id"): a for a in _master_get("/state").get("agvs", [])}
    agv = agvs.get(master_id)
    if agv is None or not agv.get("has_pose"):
        raise HTTPException(
            status_code=409,
            detail=f"No live pose for {master_id} on the VDA5050 "
            "master — is the real adapter running and the robot localized?",
        )
    last = agv.get("last_node_id")
    if last:
        return logical_graph_node(last) or last
    return snap_to_node(agv["x"], agv["y"], nodes)


def get_robot_locations(dry_run: bool) -> list[dict]:
    """Return start/goal per robot.

    Live mode (dry_run=false) queries the VDA5050 master: each robot's pose
    from /state, snapped to the nearest node of the master's /map.
    """
    config = load_robot_config()
    if dry_run:
        return [
            {
                "robot_id": r["robot_id"],
                "start": _require_route(r, "dry_run", "start"),
                "goal": _require_route(r, "dry_run", "goal"),
            }
            for r in config
        ]

    nodes = _master_nodes()
    return [
        {
            "robot_id": robot["robot_id"],
            "start": resolve_live_start(robot["master_id"], nodes),
            "goal": _require_route(robot, "real", "goal"),
        }
        for robot in config
    ]


def build_robot_schedule(robot: dict) -> RobotSchedule:
    """Build one single-GoToNode crossflow Schedule envelope for one robot."""
    task_id = str(uuid4())
    schedule_id = f"blue-ocean-{robot['robot_id']}-{task_id}"
    config: dict = {
        "asset_name": robot["robot_id"],
        "coordinates": robot["goal"],
        "start_location": robot["start"],
        "task_id": task_id,
    }
    if robot.get("goal_actions"):
        config["goal_actions"] = robot["goal_actions"]
    schedule = {
        "type": "Schedule",
        "id": schedule_id,
        "payload": {
            "version": "0.1.0",
            "start": "goto",
            "ops": {
                "goto": {
                    "type": "node",
                    "builder": "GoToNode",
                    "config": config,
                    "next": {"builtin": "terminate"},
                },
            },
        },
    }
    return RobotSchedule(
        robot_id=robot["robot_id"],
        start=robot["start"],
        goal=robot["goal"],
        task_id=task_id,
        schedule_id=schedule_id,
        schedule=schedule,
    )


def publish_schedules(schedules: list[RobotSchedule], host: str, port: int) -> None:
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port)
        )
    except pika.exceptions.AMQPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach AMQP broker at {host}:{port}: {exc}",
        ) from exc

    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=AMQP_EXCHANGE, exchange_type="fanout", durable=True
        )
        for item in schedules:
            channel.basic_publish(
                exchange=AMQP_EXCHANGE,
                routing_key="",
                body=json.dumps(item.schedule),
            )
    finally:
        connection.close()


class MapNode(BaseModel):
    node_id: str
    x: float | None = None
    y: float | None = None


class NavigateToRequest(BaseModel):
    """Goal is either ``goal_node`` (a master /map node id) or master-frame
    ``x``/``y`` (snapped to the nearest map node) — exactly one form."""

    robot_id: str
    goal_node: str | None = None
    x: float | None = None
    y: float | None = None
    dry_run: bool = False
    # Optional VDA5050 node actions executed by the adapter when the robot
    # reaches the goal node. e.g. [{"action_type": "jackUp"}] for pickup,
    # [{"action_type": "jackDown"}] for delivery.
    goal_actions: list[dict] = Field(default_factory=list)


class NavigateToResponse(BaseModel):
    dry_run: bool
    broker: str
    exchange: str
    robot: RobotSchedule


def build_demo_description() -> str:
    """Markdown for the Swagger landing page: per-robot start/goal demo list.

    Built from the master ``/robots`` (start/goal per mode) so it never goes
    stale against the config. Node coordinates are intentionally NOT embedded —
    dry-run (grid) and real (ARTC) topologies differ, and the live master map is
    authoritative — so callers are pointed at ``GET /demo/nodes`` instead.
    """
    robots = _safe_robot_config()
    lines = [
        "**Click-to-navigate** demo — move individual robots to master-frame "
        "goal nodes through the full stack: scheduler → AMQP → task "
        "orchestrator → MAPF planner → VDA5050 master → robot adapters.",
        "",
        "Use the VDA Visualiser (arm a robot, click a node) or "
        "**`POST /demo/navigate-to`** for one robot at a time. MAPF "
        "coordinates multi-robot traffic automatically.",
        "",
        "All node ids are in the **master frame** (AutoXing onboard map "
        "`From Mapping 40`); Reeman adapters transform to their own frame "
        "internally.",
        "",
        "### Navigation workflow",
        "",
        "1. **`POST /demo/navigate-to`** — send one robot to a goal node "
        "(or master-frame x/y snapped to the nearest node).",
        "2. Poll the VDA5050 master `/state` or the dashboard WebSocket for "
        "progress.",
        "3. **`POST /demo/cancel-navigation/{robot_id}`** — stop the robot's "
        "movement and clear a stuck mission or MAPF batch for one robot.",
        "",
        "### Demo list — robots & goals",
        "",
        "| Robot | master_id | Dry-run start | Dry-run goal | Real goal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in robots:
        dry = r.get("dry_run", {})
        real = r.get("real", {})
        lines.append(
            f"| `{r['robot_id']}` | `{r['master_id']}` "
            f"| `{dry.get('start', '—')}` | `{dry.get('goal', '—')}` "
            f"| `{real.get('goal', '—')}` |"
        )
    if not robots:
        lines.append("| _(robot config unavailable)_ | | | | |")
    lines += [
        "",
        "### Available nodes",
        "",
        "Node ids are grid strings `\"col,row\"`. The dry-run and real demos use "
        "different topologies (real coords come from the master map / GET /demo/nodes), "
        "so for the authoritative node list **with live coordinates** call "
        "**`GET /demo/nodes`** (it reads the VDA5050 master `/map`). Real demo "
        "starts come from each robot's live `/state` pose snapped to the nearest "
        "map node at run time (limit `SNAP_MAX_DIST_M`, default 3 m).",
        "",
        "### Direct navigate (bypass)",
        "",
        "**`POST /demo/direct-navigate`** sends spellbook-equivalent navigate "
        "commands straight to each robot's REST API. No AMQP, MAPF, or VDA5050 "
        "master — use for physical debugging when the full stack rejects orders "
        "(e.g. pose outside `allowed_deviation_xy`). Coordinates are master-frame; "
        "Reeman goals are transformed via the master `/transform` before dispatch.",
        "",
        "### Recovery (stuck MAPF / stitch state)",
        "",
        "When departure-blocker bookkeeping or stitch guards leave MAPF stuck, "
        "call **`POST /demo/mapf-all-idle`** instead of restarting the master "
        "and adapters. This clears stored plans and dispatch records on the "
        "VDA5050 master and publishes a ``MapfReset`` so the planner drops its "
        "task batch and syncs agent positions from live `/state` poses. Use "
        "``?wait=true`` to wait until robots look idle on the "
        "master first; default is force-clear.",
    ]
    return "\n".join(lines)


@router.get("/nodes", response_model=list[MapNode])
def list_nodes() -> list[MapNode]:
    """Master /map topology nodes (master-frame coords) — valid navigate-to goals."""
    return [
        MapNode(node_id=n["node_id"], x=n.get("x"), y=n.get("y"))
        for n in _master_nodes()
    ]


@router.post(
    "/navigate-to",
    response_model=NavigateToResponse,
    summary="Navigate To Nodes [MAPF]",
)
def navigate_to(req: NavigateToRequest) -> NavigateToResponse:
    """Move one robot to a master-frame goal through the full pipeline.

    Publishes a single-GoToNode Schedule to the task orchestrator, which fires
    an ``amr_mapf`` TaskRequest at the planner; the plan is dispatched by the
    VDA5050 master as a real order.

    The goal comes from the request (``goal_node`` or master-frame ``x``/``y``);
    real demo starts come from live localization. All coordinates are in the
    master frame.
    """
    config = {r["robot_id"]: r for r in load_robot_config()}
    robot_cfg = config.get(req.robot_id)
    if robot_cfg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown robot_id {req.robot_id!r} — valid: {sorted(config)}.",
        )
    if (req.goal_node is None) == (req.x is None or req.y is None):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one goal form: goal_node, or x and y.",
        )

    nodes = _master_nodes()
    if req.goal_node is not None:
        if not any(n["node_id"] == req.goal_node for n in nodes):
            raise HTTPException(
                status_code=404,
                detail=f"goal_node {req.goal_node!r} is not on the master map "
                f"— valid: {sorted(n['node_id'] for n in nodes)}.",
            )
        goal = req.goal_node
    else:
        goal = snap_to_node(req.x, req.y, nodes)

    start = (
        _require_route(robot_cfg, "dry_run", "start")
        if req.dry_run
        else resolve_live_start(robot_cfg["master_id"], nodes)
    )

    schedule = build_robot_schedule(
        {"robot_id": req.robot_id, "start": start, "goal": goal,
         "goal_actions": req.goal_actions}
    )
    host = os.environ.get("AMQP_HOST", "amqp-broker")
    port = int(os.environ.get("AMQP_PORT", "5672"))
    publish_schedules([schedule], host, port)

    return NavigateToResponse(
        dry_run=req.dry_run,
        broker=f"{host}:{port}",
        exchange=AMQP_EXCHANGE,
        robot=schedule,
    )


from demo_routes.direct_navigate import router as direct_navigate_router  # noqa: E402
from demo_routes.mapf_reset import router as mapf_reset_router  # noqa: E402
from demo_routes.mission import router as mission_router  # noqa: E402
from demo_routes.pick_rack import router as pick_rack_router  # noqa: E402

router.include_router(direct_navigate_router)
router.include_router(mapf_reset_router)
router.include_router(mission_router)
router.include_router(pick_rack_router)
