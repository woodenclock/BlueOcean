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

"""Direct robot navigate — bypass MAPF, AMQP, and VDA5050 master.

POST spellbook-equivalent navigate commands to each robot's REST API.
Master-frame goals are transformed to Reeman robot-frame before dispatch.
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Imported after blue_ocean module init; _master_get is the shared VDA5050
# master HTTP helper (the master is the single map/transform/robots authority).
from demo_routes.blue_ocean import _master_get, load_robot_config
from demo_routes.reeman_spellbook_loader import load_navigate

router = APIRouter(tags=["Demo"])

AUTOXING_CREATOR = "blue_ocean_direct_nav"
HTTP_TIMEOUT_S = 10.0
POLL_INTERVAL_S = 0.5
TERMINAL_AUTOXING_STATES = frozenset({"succeeded", "failed", "cancelled"})


@dataclass(frozen=True)
class SimilarityTransform:
    s: float
    r: float
    tx: float
    ty: float

    @classmethod
    def from_yaml_params(cls, tx: float, ty: float, theta: float, scale: float) -> SimilarityTransform:
        return cls(
            s=scale * math.cos(theta),
            r=scale * math.sin(theta),
            tx=tx,
            ty=ty,
        )

    def to_robot(self, mx: float, my: float, mtheta: float | None) -> tuple[float, float, float | None]:
        det = self.s * self.s + self.r * self.r
        dx, dy = mx - self.tx, my - self.ty
        rx = (self.s * dx + self.r * dy) / det
        ry = (-self.r * dx + self.s * dy) / det
        if mtheta is None:
            return rx, ry, None
        rotation = math.atan2(self.r, self.s)
        rtheta = math.atan2(math.sin(mtheta - rotation), math.cos(mtheta - rotation))
        return rx, ry, rtheta


class GoalCoords(BaseModel):
    x: float
    y: float
    theta: float | None = None
    goal_node: str | None = None


class DispatchedCoords(BaseModel):
    x: float
    y: float
    theta: float | None = None


class DirectNavigateRequest(BaseModel):
    robot_id: str
    goal_node: str | None = None
    x: float | None = None
    y: float | None = None
    theta: float | None = None
    wait: bool = False


class DirectNavigateResponse(BaseModel):
    robot_id: str
    goal: GoalCoords
    dispatched: DispatchedCoords
    robot_frame: DispatchedCoords | None = None
    robot_url: str
    robot_response: dict[str, Any]
    arrived: bool | None = None
    wait: bool


@lru_cache
def _master_map_nodes() -> dict[str, dict[str, float]]:
    """Master-frame node coords from the VDA5050 master /map (node_id -> {x,y}).

    Replaces the previously-bundled gametl_demo_map.real.json copy — the master
    is now the single source of map truth."""
    nodes = _master_get("/map").get("nodes", [])
    if not nodes:
        # Don't let lru_cache memoize an empty map (master up but not yet
        # loaded); raise so the next call retries once the map is available.
        raise HTTPException(status_code=502, detail="VDA5050 master returned an empty /map.")
    return {n["node_id"]: {"x": float(n["x"]), "y": float(n["y"])} for n in nodes}


def resolve_goal(req: DirectNavigateRequest) -> GoalCoords:
    has_node = req.goal_node is not None
    has_xy = req.x is not None and req.y is not None
    if has_node == has_xy:
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one goal form: goal_node, or x and y.",
        )
    if req.goal_node is not None:
        node = _master_map_nodes().get(req.goal_node)
        if node is None:
            raise HTTPException(
                status_code=404,
                detail=f"goal_node {req.goal_node!r} is not on the master map "
                f"— valid: {sorted(_master_map_nodes())}.",
            )
        return GoalCoords(x=node["x"], y=node["y"], theta=req.theta, goal_node=req.goal_node)
    assert req.x is not None and req.y is not None
    return GoalCoords(x=req.x, y=req.y, theta=req.theta)


def _robot_endpoint(robot: dict) -> str:
    """Each robot's REST host comes from its `endpoint` in robots.yaml (served by
    the master /robots) — the single source of truth, so multiple robots of the
    same type each hit their own host."""
    endpoint = (robot.get("endpoint") or "").strip()
    if not endpoint:
        raise HTTPException(
            status_code=503,
            detail=f"No `endpoint` set for {robot.get('robot_id')!r} in robots.yaml — "
            "direct navigate requires the robot's REST host.",
        )
    return endpoint


def _autoxing_base_url(robot: dict) -> str:
    return _robot_endpoint(robot).rstrip("/")


def _reeman_base_url(robot: dict) -> str:
    host = _robot_endpoint(robot)
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"http://{host}".rstrip("/")


@lru_cache
def _load_reeman_transform(adapter_key: str) -> SimilarityTransform:
    """Reeman robot->master similarity transform from the master /transform
    (served from the canonical maps/map_transforms.yaml). ``adapter_key`` is the
    robot's robot_id, so each Reeman uses its OWN adapters.<key> entry."""
    data = _master_get("/transform")
    try:
        params = data["adapters"][adapter_key]["robot_to_master"]
        return SimilarityTransform.from_yaml_params(
            float(params["tx"]),
            float(params["ty"]),
            float(params["theta"]),
            float(params.get("scale", 1.0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Transform for adapter {adapter_key!r} unavailable from master "
            f"/transform: {exc}",
        ) from exc


def _robot_post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = requests.post(url, json=payload, timeout=HTTP_TIMEOUT_S)
        resp.raise_for_status()
    except requests.RequestException as exc:
        detail = str(exc)
        if exc.response is not None:
            try:
                detail = f"{exc} — body: {exc.response.text[:500]}"
            except Exception:  # noqa: BLE001
                pass
        raise HTTPException(status_code=502, detail=f"Robot request failed: {detail}") from exc
    try:
        body = resp.json()
    except ValueError:
        return {"raw": resp.text}
    return body if isinstance(body, dict) else {"raw": body}


def dispatch_autoxing(
    x: float, y: float, theta: float | None, base: str
) -> tuple[str, dict[str, Any], DispatchedCoords]:
    # Position-only by default (RESET / Direct Control omit theta); target_ori only
    # when the request body includes an explicit theta override.
    url = f"{base}/chassis/moves"
    payload: dict[str, Any] = {
        "creator": AUTOXING_CREATOR,
        "type": "standard",
        "target_x": x,
        "target_y": y,
    }
    if theta is not None:
        payload["target_ori"] = theta
    return url, _robot_post(url, payload), DispatchedCoords(x=x, y=y, theta=theta)


def dispatch_reeman(
    x: float, y: float, theta: float | None, base: str, tf: SimilarityTransform
) -> tuple[str, dict[str, Any], DispatchedCoords, DispatchedCoords]:
    # Master-frame goal → robot frame; heading stays None unless the request
    # includes an explicit theta override. Spellbook navigate_reeman computes
    # bearing via atan2 when target_ori is None.
    rx, ry, rtheta = tf.to_robot(x, y, theta)
    url = f"{base}/cmd/nav"
    try:
        nav = load_navigate(base)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    robot_response = nav.navigate_reeman(rx, ry, rtheta)
    if robot_response is None:
        raise HTTPException(
            status_code=502,
            detail=f"Reeman navigate failed for goal ({rx}, {ry}) via spellbook.",
        )
    return (
        url,
        robot_response,
        DispatchedCoords(x=x, y=y, theta=theta),
        DispatchedCoords(x=rx, y=ry, theta=rtheta),
    )


def _wait_timeout_s() -> float:
    return float(os.environ.get("DIRECT_NAV_WAIT_TIMEOUT_S", "300"))


def wait_reeman(base: str) -> bool:
    url = f"{base}/reeman/nav_status"
    deadline = time.monotonic() + _wait_timeout_s()
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=HTTP_TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            time.sleep(POLL_INTERVAL_S)
            continue
        if isinstance(data, dict) and data.get("res") == 3 and data.get("reason") == 0:
            return True
        if isinstance(data, dict) and data.get("res") == 3 and data.get("reason") not in (None, 0):
            return False
        time.sleep(POLL_INTERVAL_S)
    raise HTTPException(status_code=504, detail="Timed out waiting for Reeman navigation to complete.")


def wait_autoxing(move_id: int | None, base: str) -> bool | None:
    if move_id is None:
        return None
    url = f"{base}/chassis/moves/{int(move_id)}"
    deadline = time.monotonic() + _wait_timeout_s()
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=HTTP_TIMEOUT_S)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            time.sleep(POLL_INTERVAL_S)
            continue
        state = data.get("state") if isinstance(data, dict) else None
        if isinstance(state, str) and state in TERMINAL_AUTOXING_STATES:
            return state == "succeeded"
        time.sleep(POLL_INTERVAL_S)
    raise HTTPException(status_code=504, detail="Timed out waiting for AutoXing navigation to complete.")


def _extract_autoxing_move_id(robot_response: dict[str, Any]) -> int | None:
    move_id = robot_response.get("id")
    if isinstance(move_id, int):
        return move_id
    if isinstance(move_id, str) and move_id.isdigit():
        return int(move_id)
    return None


def _set_master_last_node(robot_id: str, goal: GoalCoords) -> None:
    """Best-effort: pin the master's ``last_node_id`` to the direct-nav
    destination. direct-navigate bypasses VDA5050, so the order-driven
    last_node_id would stay stale and the scheduler/MAPF planner would plan from
    the wrong node; this snaps it to where we just sent the robot. Failures are
    swallowed — the navigate already succeeded."""
    body: dict = (
        {"node_id": goal.goal_node}
        if goal.goal_node
        else {"x": goal.x, "y": goal.y}
    )
    master_url = os.environ.get("MASTER_URL", "http://vda5050:8000").rstrip("/")
    try:
        requests.post(
            f"{master_url}/state/last-node/{robot_id}", json=body, timeout=5
        )
    except requests.RequestException:
        pass


@router.post(
    "/direct-navigate",
    response_model=DirectNavigateResponse,
    summary="Direct Navigate [Direct-API to Robot | No MAPF]",
)
def direct_navigate(req: DirectNavigateRequest) -> DirectNavigateResponse:
    """Navigate one robot directly via spellbook-equivalent REST (no MAPF/VDA5050).

    Accepts master-frame ``goal_node`` or ``x``/``y``. Reeman goals are
    transformed to robot-frame coordinates using the master ``/transform`` before dispatch.

    **Heading:** ``theta`` is optional. When omitted (the default for robot-card
    Reset and Direct Control x/y sends), dispatch delegates to spellbook
    ``navigate_reeman`` which computes heading toward the goal. Pass ``theta``
    only for an explicit manual heading override.

    Robot is routed by manufacturer (Autoxing/Reeman), so any robot in
    maps/robots.yaml works — including multiple of the same type (reeman-1,
    reeman-2-blue, ...). ``robot_id`` may be the unified robot_id or the serial.
    Each robot's REST host comes from its ``endpoint`` in robots.yaml, and Reeman
    goals use that robot's own map_transforms.yaml entry (adapters.<robot_id>).
    """
    robots = load_robot_config()
    robot = next(
        (
            r
            for r in robots
            if req.robot_id in (r.get("robot_id"), r.get("master_id"), r.get("serial_number"))
        ),
        None,
    )
    if robot is None:
        valid = sorted(r.get("robot_id") for r in robots if r.get("robot_id"))
        raise HTTPException(
            status_code=404,
            detail=f"Unknown robot_id {req.robot_id!r} — valid robot_ids: {valid}.",
        )

    robot_id = robot["robot_id"]
    manufacturer = (robot.get("manufacturer") or "").strip().lower()

    goal = resolve_goal(req)
    robot_frame: DispatchedCoords | None = None
    arrived: bool | None = None

    if manufacturer == "autoxing":
        base = _autoxing_base_url(robot)
        robot_url, robot_response, dispatched = dispatch_autoxing(goal.x, goal.y, goal.theta, base)
        if req.wait:
            arrived = wait_autoxing(_extract_autoxing_move_id(robot_response), base)
    elif manufacturer == "reeman":
        base = _reeman_base_url(robot)
        tf = _load_reeman_transform(robot_id)
        robot_url, robot_response, dispatched, robot_frame = dispatch_reeman(
            goal.x, goal.y, goal.theta, base, tf
        )
        if req.wait:
            arrived = wait_reeman(base)
    else:
        raise HTTPException(
            status_code=501,
            detail=f"Direct navigate not implemented for manufacturer "
            f"{robot.get('manufacturer')!r} (robot {robot_id!r}).",
        )

    # Snap the master's last_node_id to where we sent the robot (direct-navigate
    # bypasses VDA5050, so the order-driven last_node_id would otherwise stay
    # stale and the scheduler/MAPF planner would plan from the wrong node).
    _set_master_last_node(robot_id, goal)

    return DirectNavigateResponse(
        robot_id=robot_id,
        goal=goal,
        dispatched=dispatched,
        robot_frame=robot_frame,
        robot_url=robot_url,
        robot_response=robot_response,
        arrived=arrived,
        wait=req.wait,
    )
