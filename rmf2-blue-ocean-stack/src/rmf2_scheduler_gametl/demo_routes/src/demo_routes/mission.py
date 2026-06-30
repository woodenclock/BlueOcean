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

"""Multi-goal **mission** runner — drive one robot through an ordered list of
goal nodes (up to 3 from the RMF UI) through the full MAPF/VDA5050 stack.

Why a runner instead of one Schedule with N chained GoToNode ops: the
orchestrator's GoToNode completes (publishes TaskStatus) as soon as the planner
*dispatches* a leg's order to the VDA5050 master — NOT when the robot physically
arrives (see blue_ocean_planner_service.solve_batch). Chaining ops would fire
all legs at once. So sequencing must wait for *arrival*, which only something
with access to the master /state can do — hence this scheduler-side runner.

Each leg reuses the existing single-goal path (build_robot_schedule +
publish_schedules -> orchestrator -> MAPF -> VDA5050 order). Between legs the
runner polls the master /state until the robot reaches the leg's goal node.

**Rack pick/drop**: when a leg's goal is a rack node (see ``demo_routes.racks``)
an **AutoXing** robot jacks on arrival via the master's
``/actions/jack/{robot_id}/{direction}`` endpoint when ``goal_jacks`` supplies
an explicit direction ("up" = pick / "down" = drop). Reeman legs reach rack
nodes but skip jack. Use ``POST /demo/rack-direct`` for AutoXing pick/drop via
the robot REST API (no MAPF). After a rack leg the next leg starts from the
rack's **approach** node (e.g. ``3,5`` after pick/drop at ``2,5`` or ``3,4``),
not the rack node itself.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from demo_routes.blue_ocean import (
    _master_get,
    _master_nodes,
    _require_route,
    build_robot_schedule,
    load_robot_config,
    publish_schedules,
    resolve_live_start,
    snap_to_node,
)
from demo_routes.mapf_reset import reset_robot_mapf_coordination
from demo_routes.racks import get_rack_nodes, rack_departure_node

# No prefix: included under blue_ocean's APIRouter(prefix="/demo"), like
# direct_navigate/mapf_reset — so these become /demo/navigate-mission etc.
router = APIRouter(tags=["Demo"])

# Jack states that mean "carrying a load" (so the next rack action is a drop).
_JACK_UP_STATES = frozenset({"up", "hold"})

MISSION_POLL_INTERVAL_S = float(os.environ.get("MISSION_POLL_INTERVAL_S", "1.0"))
MISSION_ARRIVAL_TIMEOUT_S = float(os.environ.get("MISSION_ARRIVAL_TIMEOUT_S", "300"))
MISSION_JACK_TIMEOUT_S = float(os.environ.get("MISSION_JACK_TIMEOUT_S", "90"))
# After dispatching a leg, wait this long for the robot to start driving before
# reporting a plan/dispatch failure to the UI (covers CBS batch window + timeout).
MISSION_PLAN_WAIT_S = float(os.environ.get("MISSION_PLAN_WAIT_S", "45"))
# How close (m) the live pose must be to the goal node to count as "arrived"
# when the master hasn't reported a matching last_node_id.
MISSION_ARRIVE_DIST_M = float(os.environ.get("MISSION_ARRIVE_DIST_M", "0.6"))


# --- Mission state (in-memory, one active mission per robot) ----------------

_missions: dict[str, dict] = {}
_missions_lock = threading.Lock()


class NavigateMissionRequest(BaseModel):
    """Drive one robot through ``goals`` in order. Each goal is a master /map
    node id; rack nodes trigger a jack action on arrival.

    ``goal_jacks`` (optional, index-aligned with ``goals``) sets an **explicit**
    jack direction per rack leg for **AutoXing** — "up" to pick, "down" to drop.
    Reeman legs skip jack even at rack nodes."""

    robot_id: str
    goals: list[str] = Field(..., min_length=1, max_length=8)
    goal_jacks: list[str | None] | None = None
    dry_run: bool = False


class MissionLeg(BaseModel):
    goal: str
    is_rack: bool = False
    status: str = "pending"  # pending | navigating | arrived | jacking | done | error
    jack: str | None = None  # "up" (pick) | "down" (drop) | None
    detail: str | None = None


class MissionState(BaseModel):
    robot_id: str
    dry_run: bool
    status: str  # running | completed | error | cancelled
    current_leg: int
    legs: list[MissionLeg]
    detail: str | None = None


class CancelNavigationResponse(BaseModel):
    robot_id: str
    mission_cleared: bool
    planner_reset_published: bool
    robot_stopped: bool


def reset_robot_demo_state(
    robot_id: str,
    reason: str | None = None,
) -> CancelNavigationResponse:
    """Stop one robot, clear its mission, and reset MAPF coordination.

    Idempotent — safe to call when the robot is already idle."""
    reset_reason = reason or f"cancel_navigation:{robot_id}"
    mission_cleared = False
    with _missions_lock:
        mission = _missions.get(robot_id)
        if mission is not None:
            mission["cancelled"] = True
            mission["status"] = "cancelled"
            mission_cleared = True

    robot_stopped = False
    try:
        robot_stopped = bool(_master_post(f"/actions/stop/{robot_id}").get("success"))
    except RuntimeError:
        robot_stopped = False

    _, planner_reset_published = reset_robot_mapf_coordination(
        robot_id, reason=reset_reason
    )

    with _missions_lock:
        _missions.pop(robot_id, None)

    return CancelNavigationResponse(
        robot_id=robot_id,
        mission_cleared=mission_cleared,
        planner_reset_published=planner_reset_published,
        robot_stopped=robot_stopped,
    )


class RackDirectLeg(BaseModel):
    node: str
    jack: str  # "up" (pick) | "down" (drop)


class RackDirectRequest(BaseModel):
    """Pick/drop at rack nodes using the **direct** robot REST API — no MAPF,
    AMQP, or VDA5050. For each leg the runner navigates straight to the node's
    master-frame coords (blocking on the robot's own move status) then jacks
    up/down, waiting for the jack to settle before the next leg."""

    robot_id: str
    legs: list[RackDirectLeg] = Field(..., min_length=1, max_length=4)


# --- master helpers ---------------------------------------------------------

def _master_post(path: str) -> dict:
    """POST (no body) to the VDA5050 master — used for /actions/jack."""
    master_url = os.environ.get("MASTER_URL", "http://vda5050:8000")
    url = f"{master_url.rstrip('/')}{path}"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"master POST {url} failed: {exc}") from exc


def _agv_snapshot(robot_id: str) -> dict | None:
    agvs = _master_get("/state").get("agvs", [])
    return next((a for a in agvs if a.get("robot_id") == robot_id), None)


def _nearest_node_id(x: float, y: float, nodes: list[dict]) -> tuple[str | None, float]:
    if not nodes:
        return None, float("inf")
    node = min(nodes, key=lambda n: (n["x"] - x) ** 2 + (n["y"] - y) ** 2)
    dist = ((node["x"] - x) ** 2 + (node["y"] - y) ** 2) ** 0.5
    return node["node_id"], dist


# --- leg execution ----------------------------------------------------------

def _dispatch_leg(robot_id: str, start: str, goal: str, dry_run: bool) -> None:
    """Publish a single-GoToNode Schedule for this leg (full MAPF stack)."""
    schedule = build_robot_schedule(
        {"robot_id": robot_id, "start": start, "goal": goal, "goal_actions": []}
    )
    host = os.environ.get("AMQP_HOST", "amqp-broker")
    port = int(os.environ.get("AMQP_PORT", "5672"))
    publish_schedules([schedule], host, port)


def _is_mission_cancelled(robot_id: str) -> bool:
    with _missions_lock:
        mission = _missions.get(robot_id)
        return mission is not None and mission.get("cancelled", False)


def _at_goal_stopped(agv: dict, goal: str, goal_node: dict | None) -> bool:
    """True when the AGV is at ``goal`` and no longer driving."""
    if agv.get("driving", True):
        return False
    at_node = agv.get("last_node_id") == goal
    near_goal = (
        agv.get("has_pose")
        and goal_node is not None
        and _nearest_node_id(agv["x"], agv["y"], [goal_node])[1]
        <= MISSION_ARRIVE_DIST_M
    )
    return at_node or near_goal


def _wait_for_leg_start(robot_id: str, goal: str, nodes: list[dict]) -> tuple[bool, str | None]:
    """After publishing a leg, wait until MAPF dispatches and the robot moves.

    Returns ``(True, None)`` once driving starts or the robot is already at the
    goal. Returns ``(False, detail)`` when the planner never dispatches a route
    (unreachable goal, CBS timeout, etc.) so the UI can be notified quickly
    instead of waiting for the full arrival timeout.
    """
    goal_node = next((n for n in nodes if n["node_id"] == goal), None)
    deadline = time.monotonic() + MISSION_PLAN_WAIT_S
    while time.monotonic() < deadline:
        if _is_mission_cancelled(robot_id):
            return False, "cancelled by user"
        try:
            agv = _agv_snapshot(robot_id)
        except HTTPException:
            agv = None
        if agv is not None:
            if agv.get("driving"):
                return True, None
            if _at_goal_stopped(agv, goal, goal_node):
                return True, None
        time.sleep(MISSION_POLL_INTERVAL_S)
    return False, (
        "MAPF did not dispatch a route — the goal may be unreachable "
        "(blocked by another robot) or the planner timed out"
    )


def _wait_for_arrival(robot_id: str, goal: str, nodes: list[dict]) -> bool:
    """Poll the master /state until the robot has *arrived and stopped* at
    ``goal``: it is at the node (reported last_node_id, or pose within
    MISSION_ARRIVE_DIST_M) **and** no longer driving.

    The not-driving gate matters for rack legs: the next step jacks, and the
    fork must not move until the robot has physically settled at the node.
    Without it the pose can cross the arrival radius (or the node be reported)
    while the robot is still moving, firing the jack too early. ``driving`` is
    the master's pass-through of the VDA5050 state flag; treat unknown
    (None / missing) as still moving.
    """
    goal_node = next((n for n in nodes if n["node_id"] == goal), None)
    deadline = time.monotonic() + MISSION_ARRIVAL_TIMEOUT_S
    while time.monotonic() < deadline:
        if _is_mission_cancelled(robot_id):
            return False
        try:
            agv = _agv_snapshot(robot_id)
        except HTTPException:
            agv = None
        if agv is not None and _at_goal_stopped(agv, goal, goal_node):
            return True
        time.sleep(MISSION_POLL_INTERVAL_S)
    return False


def _wait_for_jack(robot_id: str, target: str) -> bool:
    """Poll until the jack settles into its target stable state ('up'/'down')."""
    stable = _JACK_UP_STATES if target == "up" else {"down"}
    deadline = time.monotonic() + MISSION_JACK_TIMEOUT_S
    while time.monotonic() < deadline:
        if _is_mission_cancelled(robot_id):
            return False
        try:
            agv = _agv_snapshot(robot_id)
        except HTTPException:
            agv = None
        if agv is not None and agv.get("jack_state") in stable:
            return True
        time.sleep(MISSION_POLL_INTERVAL_S)
    return False


def _set_leg(robot_id: str, idx: int, **fields) -> None:
    with _missions_lock:
        mission = _missions.get(robot_id)
        if mission is None:
            return
        mission["current_leg"] = idx
        leg = mission["legs"][idx]
        leg.update(fields)


def _finish_mission(robot_id: str, status: str, detail: str | None = None) -> None:
    with _missions_lock:
        mission = _missions.get(robot_id)
        if mission is None:
            return
        mission["status"] = status
        if detail:
            mission["detail"] = detail


def _run_mission(robot_id: str, manufacturer: str, goals: list[str],
                 dry_run: bool, first_start: str,
                 goal_jacks: list[str | None] | None = None) -> None:
    """Background thread: drive the robot leg-by-leg, jack at rack legs."""
    is_autoxing = manufacturer.strip().lower() == "autoxing"
    prev = first_start
    try:
        nodes = _master_nodes()
        for idx, goal in enumerate(goals):
            if _is_mission_cancelled(robot_id):
                _finish_mission(robot_id, "cancelled", "cancelled by user")
                return
            _set_leg(robot_id, idx, status="navigating")
            _dispatch_leg(robot_id, prev, goal, dry_run)
            started, plan_detail = _wait_for_leg_start(robot_id, goal, nodes)
            if not started:
                if plan_detail == "cancelled by user":
                    _finish_mission(robot_id, "cancelled", plan_detail)
                else:
                    _set_leg(robot_id, idx, status="error", detail=plan_detail)
                    _finish_mission(
                        robot_id, "error", f"leg {idx} ({goal}): {plan_detail}"
                    )
                return
            if not _wait_for_arrival(robot_id, goal, nodes):
                if _is_mission_cancelled(robot_id):
                    _finish_mission(robot_id, "cancelled", "cancelled by user")
                else:
                    _set_leg(robot_id, idx, status="error",
                             detail="timed out waiting for arrival")
                    _finish_mission(robot_id, "error",
                                    f"leg {idx} ({goal}): arrival timeout")
                return
            _set_leg(robot_id, idx, status="arrived")

            if goal in get_rack_nodes():
                explicit = goal_jacks[idx] if goal_jacks else None
                direction = explicit if is_autoxing else None
                if direction is None:
                    skip_reason = (
                        "rack reached; jack skipped (Reeman)"
                        if not is_autoxing
                        else "rack reached; jack skipped (no direction)"
                    )
                    _set_leg(robot_id, idx, status="done", detail=skip_reason)
                else:
                    action = "pick" if direction == "up" else "drop"
                    _set_leg(robot_id, idx, status="jacking",
                             jack=direction, detail=f"{action} (jack {direction})")
                    try:
                        _master_post(f"/actions/jack/{robot_id}/{direction}")
                    except RuntimeError as exc:
                        _set_leg(robot_id, idx, status="error", detail=str(exc))
                        _finish_mission(robot_id, "error",
                                        f"leg {idx} ({goal}): jack failed")
                        return
                    _wait_for_jack(robot_id, direction)
                    _set_leg(robot_id, idx, status="done",
                             jack=direction, detail=f"{action} complete")
            else:
                _set_leg(robot_id, idx, status="done")

            prev = rack_departure_node(goal) if goal in get_rack_nodes() else goal
        _finish_mission(robot_id, "completed")
    except Exception as exc:  # noqa: BLE001 — surface any runner failure to status
        _finish_mission(robot_id, "error", f"mission crashed: {exc}")


def _run_rack_direct(robot_id: str, legs: list[dict]) -> None:
    """Background thread: per leg, direct-navigate to the node (blocking on the
    robot's OWN move status — no MAPF/AMQP/VDA5050) then jack, gating the next
    leg on the jack settling. Backs the autoxing rack card's pick/drop row."""
    # Imported lazily to avoid any package import-order coupling at module load.
    from demo_routes.direct_navigate import DirectNavigateRequest, direct_navigate

    try:
        for idx, leg in enumerate(legs):
            if _is_mission_cancelled(robot_id):
                _finish_mission(robot_id, "cancelled", "cancelled by user")
                return
            node = leg["node"]
            direction = leg["jack"]
            action = "pick" if direction == "up" else "drop"

            _set_leg(robot_id, idx, status="navigating")
            try:
                # wait=True blocks until the AutoXing move reaches a terminal
                # state, so the jack only fires once the robot has arrived.
                direct_navigate(
                    DirectNavigateRequest(robot_id=robot_id, goal_node=node, wait=True)
                )
            except HTTPException as exc:
                if _is_mission_cancelled(robot_id):
                    _finish_mission(robot_id, "cancelled", "cancelled by user")
                else:
                    _set_leg(robot_id, idx, status="error", detail=str(exc.detail))
                    _finish_mission(robot_id, "error",
                                    f"leg {idx} ({node}): navigate failed")
                return
            if _is_mission_cancelled(robot_id):
                _finish_mission(robot_id, "cancelled", "cancelled by user")
                return
            _set_leg(robot_id, idx, status="arrived")

            _set_leg(robot_id, idx, status="jacking", jack=direction,
                     detail=f"{action} (jack {direction})")
            try:
                _master_post(f"/actions/jack/{robot_id}/{direction}")
            except RuntimeError as exc:
                _set_leg(robot_id, idx, status="error", detail=str(exc))
                _finish_mission(robot_id, "error",
                                f"leg {idx} ({node}): jack failed")
                return
            _wait_for_jack(robot_id, direction)
            _set_leg(robot_id, idx, status="done", jack=direction,
                     detail=f"{action} complete")
        _finish_mission(robot_id, "completed")
    except Exception as exc:  # noqa: BLE001 — surface any runner failure to status
        _finish_mission(robot_id, "error", f"rack-direct crashed: {exc}")


# --- endpoints --------------------------------------------------------------

@router.get("/racks", summary="Rack nodes (AutoXing pick/drop)")
def list_racks() -> dict[str, str | None]:
    """Rack node id -> approach node id. AutoXing rack legs jack when
    ``goal_jacks`` is set or via ``POST /demo/rack-direct``; Reeman skips jack."""
    return get_rack_nodes()


@router.post(
    "/navigate-mission",
    response_model=MissionState,
    status_code=202,
    summary="Navigate Mission [MAPF · multi-goal · rack pick/drop]",
)
def navigate_mission(
    req: Annotated[
        NavigateMissionRequest,
        Body(openapi_examples={
            "autoxing_pick_drop": {
                "summary": "AutoXing: pick at West (2,5) → drop at Human Arm (3,10)",
                "description": "Two legs through full MAPF with explicit jack "
                "directions at each rack node.",
                "value": {"robot_id": "autoxing-1",
                          "goals": ["2,5", "3,10"], "dry_run": False,
                          "goal_jacks": ["up", "down"]},
            },
        }),
    ],
) -> MissionState:
    """Drive one robot through ``goals`` in order via the full MAPF/VDA5050
    stack, waiting for arrival between legs. AutoXing rack legs jack when
    ``goal_jacks`` is set; Reeman skips jack. Returns immediately (202); poll
    ``GET /demo/mission/{robot_id}``.
    """
    config = {r["robot_id"]: r for r in load_robot_config()}
    robot_cfg = config.get(req.robot_id)
    if robot_cfg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown robot_id {req.robot_id!r} — valid: {sorted(config)}.",
        )

    nodes = _master_nodes()
    valid_ids = {n["node_id"] for n in nodes}
    bad = [g for g in req.goals if g not in valid_ids]
    if bad:
        raise HTTPException(
            status_code=404,
            detail=f"goals {bad} are not on the master map — valid: {sorted(valid_ids)}.",
        )

    if req.goal_jacks is not None:
        if len(req.goal_jacks) != len(req.goals):
            raise HTTPException(
                status_code=422,
                detail=f"goal_jacks (len {len(req.goal_jacks)}) must match goals "
                f"(len {len(req.goals)}).",
            )
        bad_jacks = [j for j in req.goal_jacks if j not in ("up", "down", None)]
        if bad_jacks:
            raise HTTPException(
                status_code=422,
                detail=f"goal_jacks entries must be 'up', 'down' or null — got {bad_jacks}.",
            )

    with _missions_lock:
        active = _missions.get(req.robot_id)
        if active is not None and active["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail=f"{req.robot_id} already has a running mission — wait for it "
                "to finish or cancel it.",
            )

    # First leg starts from the live pose (snapped) in real mode, or the
    # configured dry-run start in dry-run mode.
    if req.dry_run:
        first_start = _require_route(robot_cfg, "dry_run", "start")
    else:
        first_start = resolve_live_start(robot_cfg["master_id"], nodes)

    legs = [
        MissionLeg(goal=g, is_rack=g in get_rack_nodes()).model_dump()
        for g in req.goals
    ]
    with _missions_lock:
        _missions[req.robot_id] = {
            "robot_id": req.robot_id,
            "dry_run": req.dry_run,
            "status": "running",
            "cancelled": False,
            "current_leg": 0,
            "legs": legs,
            "detail": None,
        }

    threading.Thread(
        target=_run_mission,
        args=(req.robot_id, robot_cfg.get("manufacturer", ""), req.goals,
              req.dry_run, first_start, req.goal_jacks),
        daemon=True,
    ).start()

    return _mission_state(req.robot_id)


@router.post(
    "/rack-direct",
    response_model=MissionState,
    status_code=202,
    summary="Rack pick/drop [Direct-API to robot · no MAPF]",
)
def rack_direct(
    req: Annotated[
        RackDirectRequest,
        Body(openapi_examples={
            "autoxing_pick": {
                "summary": "AutoXing: pick at West (1,5)",
                "description": "Drive direct to the node, then jack up.",
                "value": {"robot_id": "autoxing-1",
                          "legs": [{"node": "1,5", "jack": "up"}]},
            },
            "autoxing_loop": {
                "summary": "AutoXing: pick at West (1,5) → drop at Human Arm (3,10)",
                "description": "Full loop via the direct REST API; each jack "
                "finishes before the next leg.",
                "value": {"robot_id": "autoxing-1",
                          "legs": [{"node": "1,5", "jack": "up"},
                                   {"node": "3,10", "jack": "down"}]},
            },
        }),
    ],
) -> MissionState:
    """Pick/drop at rack nodes using the **direct** robot REST API (no MAPF). For
    each leg: navigate straight to the node then jack up/down, waiting for the
    jack to finish before the next leg. Returns 202; poll ``GET
    /demo/mission/{robot_id}``. Cancel with ``POST /demo/cancel-navigation``."""
    config = {r["robot_id"]: r for r in load_robot_config()}
    robot_cfg = config.get(req.robot_id)
    if robot_cfg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown robot_id {req.robot_id!r} — valid: {sorted(config)}.",
        )
    if (robot_cfg.get("manufacturer") or "").strip().lower() != "autoxing":
        raise HTTPException(
            status_code=422,
            detail=f"rack-direct is AutoXing-only — got {req.robot_id!r}.",
        )

    bad_jacks = [leg.jack for leg in req.legs if leg.jack not in ("up", "down")]
    if bad_jacks:
        raise HTTPException(
            status_code=422,
            detail=f"leg jack must be 'up' or 'down' — got {bad_jacks}.",
        )

    nodes = _master_nodes()
    valid_ids = {n["node_id"] for n in nodes}
    bad = [leg.node for leg in req.legs if leg.node not in valid_ids]
    if bad:
        raise HTTPException(
            status_code=404,
            detail=f"nodes {bad} are not on the master map — valid: {sorted(valid_ids)}.",
        )

    with _missions_lock:
        active = _missions.get(req.robot_id)
        if active is not None and active["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail=f"{req.robot_id} already has a running mission — wait for it "
                "to finish or cancel it.",
            )

    legs = [
        MissionLeg(goal=leg.node, is_rack=True, jack=leg.jack).model_dump()
        for leg in req.legs
    ]
    with _missions_lock:
        _missions[req.robot_id] = {
            "robot_id": req.robot_id,
            "dry_run": False,
            "status": "running",
            "cancelled": False,
            "current_leg": 0,
            "legs": legs,
            "detail": None,
        }

    threading.Thread(
        target=_run_rack_direct,
        args=(req.robot_id, [{"node": leg.node, "jack": leg.jack} for leg in req.legs]),
        daemon=True,
    ).start()

    return _mission_state(req.robot_id)


@router.get(
    "/mission/{robot_id}",
    response_model=MissionState,
    summary="Mission status for one robot",
)
def mission_status(robot_id: str) -> MissionState:
    return _mission_state(robot_id)


@router.post(
    "/cancel-navigation/{robot_id}",
    response_model=CancelNavigationResponse,
    summary="Cancel navigation for one robot",
)
def cancel_navigation(robot_id: str) -> CancelNavigationResponse:
    """Stop the mission runner (if any), physically stop the robot, clear
    in-memory mission state, and reset MAPF coordination on the master +
    planner.

    The robot stop is what actually halts the AGV — clearing mission/MAPF state
    alone leaves the dispatched order running on the robot. Best-effort: a failed
    stop still proceeds to clear state so the UI doesn't get wedged.

    Idempotent — safe when the robot is already idle (returns success)."""
    return reset_robot_demo_state(
        robot_id, reason=f"cancel_navigation:{robot_id}"
    )


def _mission_state(robot_id: str) -> MissionState:
    with _missions_lock:
        mission = _missions.get(robot_id)
        if mission is None:
            raise HTTPException(
                status_code=404, detail=f"No mission for {robot_id!r}."
            )
        return MissionState(
            robot_id=mission["robot_id"],
            dry_run=mission["dry_run"],
            status=mission["status"],
            current_leg=mission["current_leg"],
            legs=[MissionLeg(**leg) for leg in mission["legs"]],
            detail=mission["detail"],
        )
