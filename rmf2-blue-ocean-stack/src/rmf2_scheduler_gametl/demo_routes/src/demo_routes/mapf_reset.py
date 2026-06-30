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

"""MAPF coordination reset — clear planner batch and master dispatch state."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import quote

import pika
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["Demo"])

AMQP_EXCHANGE = "@RECEIVE@"


class RobotIdleSnapshot(BaseModel):
    robot_id: str
    last_node_id: str | None = None
    order_active: bool
    pending_order_count: int
    idle: bool


class MapfAllIdleResponse(BaseModel):
    waited: bool
    robots: list[RobotIdleSnapshot]
    master_reset: dict
    planner_reset_published: bool


class DemoResetRobotResult(BaseModel):
    robot_id: str
    mission_cleared: bool
    planner_reset_published: bool
    robot_stopped: bool


class DemoResetResponse(BaseModel):
    robots: list[DemoResetRobotResult]
    master_reset: dict
    planner_reset_published: bool


def _master_url() -> str:
    return os.environ.get("MASTER_URL", "http://vda5050:8000").rstrip("/")


def _idle_wait_timeout_s() -> float:
    return float(os.environ.get("MAPF_IDLE_WAIT_TIMEOUT_S", "60"))


def _master_get(path: str) -> dict:
    url = f"{_master_url()}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach VDA5050 master at {url}: {exc}",
        ) from exc


def _master_post(path: str) -> dict:
    url = f"{_master_url()}{path}"
    request = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach VDA5050 master at {url}: {exc}",
        ) from exc


def _robot_idle_snapshot(agv: dict) -> RobotIdleSnapshot:
    order_active = bool(agv.get("order_active"))
    pending = int(agv.get("pending_order_count") or 0)
    return RobotIdleSnapshot(
        robot_id=agv.get("robot_id", "?"),
        last_node_id=agv.get("last_node_id"),
        order_active=order_active,
        pending_order_count=pending,
        idle=not order_active and pending == 0,
    )


def _all_robots_idle() -> tuple[bool, list[RobotIdleSnapshot]]:
    status = _master_get("/status")
    snapshots = [_robot_idle_snapshot(agv) for agv in status.get("agvs", [])]
    if not snapshots:
        return True, snapshots
    return all(r.idle for r in snapshots), snapshots


def _wait_for_idle() -> list[RobotIdleSnapshot]:
    deadline = time.monotonic() + _idle_wait_timeout_s()
    last_snapshots: list[RobotIdleSnapshot] = []
    while time.monotonic() < deadline:
        idle, last_snapshots = _all_robots_idle()
        if idle:
            return last_snapshots
        time.sleep(0.5)
    raise HTTPException(
        status_code=504,
        detail=(
            f"Timed out after {_idle_wait_timeout_s():.0f}s waiting for all "
            "robots to be idle on the VDA5050 master "
            "(order_active=false, pending_order_count=0)."
        ),
    )


def _publish_mapf_reset(
    reason: str = "scheduler_all_idle",
    robot_id: str | None = None,
) -> None:
    host = os.environ.get("AMQP_HOST", "amqp-broker")
    port = int(os.environ.get("AMQP_PORT", "5672"))
    message: dict = {"type": "MapfReset", "reason": reason}
    if robot_id:
        message["robot_id"] = robot_id
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
        channel.basic_publish(
            exchange=AMQP_EXCHANGE,
            routing_key="",
            body=json.dumps(message),
        )
    finally:
        connection.close()


def reset_mapf_coordination(reason: str = "scheduler_all_idle") -> tuple[dict, bool]:
    """Clear master MAPF plans and notify the planner via MapfReset."""
    master_reset = _master_post("/plans/mapf/reset")
    _publish_mapf_reset(reason)
    return master_reset, True


def reset_robot_mapf_coordination(
    robot_id: str,
    reason: str | None = None,
) -> tuple[dict, bool]:
    """Clear one robot's MAPF plan on the master and drop its planner task."""
    reset_reason = reason or f"cancel_navigation:{robot_id}"
    master_reset = _master_post(f"/plans/mapf/reset/{quote(robot_id, safe='')}")
    _publish_mapf_reset(reset_reason, robot_id=robot_id)
    return master_reset, True


@router.post(
    "/mapf-all-idle",
    response_model=MapfAllIdleResponse,
    summary="Force-clear MAPF coordination state",
    description=(
        "Soft reset when MAPF departure-blocker / stitch bookkeeping is stuck. "
        "Clears stored MAPF plans and dispatch records on the VDA5050 master, "
        "cancels master-side outbound order queues, and publishes a "
        "``MapfReset`` on the AMQP fanout so the planner drops its task batch "
        "and syncs agent positions from live `/state` poses.\n\n"
        "By default this **force-clears immediately** (``wait=false``). Set "
        "``wait=true`` to poll ``/status`` until every robot looks idle first.\n\n"
        "Does **not** stop in-flight robot motion on adapters — use "
        "``POST /demo/direct-navigate`` or spellbook cancel for physical robots."
    ),
)
def mapf_all_idle(wait: bool = False) -> MapfAllIdleResponse:
    if wait:
        robots = _wait_for_idle()
    else:
        _, robots = _all_robots_idle()

    master_reset = _master_post("/plans/mapf/reset")

    try:
        _publish_mapf_reset()
        published = True
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Master reset succeeded but MapfReset publish failed: {exc}",
        ) from exc

    return MapfAllIdleResponse(
        waited=wait,
        robots=robots,
        master_reset=master_reset,
        planner_reset_published=published,
    )


@router.post(
    "/demo-reset",
    response_model=DemoResetResponse,
    summary="Full demo reset — stop all robots and clear MAPF",
    description=(
        "Demo presenter recovery without restarting Docker: for each robot in "
        "``maps/robots.yaml``, stop motion, clear scheduler missions, reset "
        "per-robot MAPF plans on the master, then publish a global ``MapfReset`` "
        "so the planner aborts any hung CBS solve and syncs live poses."
    ),
)
def demo_reset() -> DemoResetResponse:
    from demo_routes.blue_ocean import load_robot_config
    from demo_routes.mission import reset_robot_demo_state

    robot_results: list[DemoResetRobotResult] = []
    for cfg in load_robot_config():
        robot_id = cfg["robot_id"]
        result = reset_robot_demo_state(robot_id, reason="demo_reset")
        robot_results.append(
            DemoResetRobotResult(
                robot_id=result.robot_id,
                mission_cleared=result.mission_cleared,
                planner_reset_published=result.planner_reset_published,
                robot_stopped=result.robot_stopped,
            )
        )

    master_reset, planner_reset_published = reset_mapf_coordination(
        reason="demo_reset"
    )

    return DemoResetResponse(
        robots=robot_results,
        master_reset=master_reset,
        planner_reset_published=planner_reset_published,
    )
