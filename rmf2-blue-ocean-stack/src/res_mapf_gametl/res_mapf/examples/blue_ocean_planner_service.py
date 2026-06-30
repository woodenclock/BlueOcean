# Copyright (C) 2026 ROS-Industrial Consortium Asia Pacific
# Advanced Remanufacturing and Technology Centre
# A*STAR Research Entities (Co. Registration No. 199702110H)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""MAPF planner service — replaces the BFS mapf-vda5050 bridge.

Long-running flow per amr_mapf TaskRequest from the task orchestrator:

  @RECEIVE@ TaskRequest -> record task -> replan ALL known tasks with the real
  res_mapf stack (MAPFCoordinator + CBS on the master's /map/grid graph + PlanGenerator,
  departure_blockers included) -> POST each robot's plan (waypoint coords +
  departure_blockers) to the VDA5050 master REST API (/plans/mapf) ->
  TaskStatus COMPLETED back on @RECEIVE@ so the orchestrator GoToNode unblocks.

The master stores the plans; it does NOT dispatch VDA5050 orders to the AGVs
yet — that waits on the map unification (TF reeman -> autoxing frame) living
in the master.

Plans are logged at DEBUG (path + departure_blockers summary). When both robots'
tasks have arrived, CBS coordinates them (reeman first through the shared
3,1 / 3,0 corridor; autoxing waits at 2,1 behind departure_blockers).
"""

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Dict

import pika
from blue_ocean_mapf_demo import (
    MapConstrainedCBSAdapter,
    MapGraph,
    plan_to_jsonable,
)
from res_mapf_planning.mapf_solve.exceptions import NoSolutionError
from res_mapf_planning.planning.mapf_coordinator import MAPFCoordinator, PlanningError
from res_mapf_planning.planning.multi_agent_context import MultiAgentContext
from res_mapf_planning.traffic_dependencies.models.plan_id import PlanId
from res_mapf_planning.traffic_dependencies.plan_generator import PlanGenerator
from res_plan_server.models.task import Task

logger = logging.getLogger("blue_ocean_planner_service")

AMQP_EXCHANGE = "@RECEIVE@"
PLANNER_QUEUE = "@RECEIVE@-mapf-planner"

# Fallback map_id only if the master's /map/grid omits it (it shouldn't).
DEFAULT_MAP_ID = "gametl_demo"


def plan_to_payload(
    robot_id: str,
    plan,
    order_id: str,
    map_id: str,
    plan_version: int,
    task_id: str,
    profiles: Dict[str, dict],
    goal_actions: list | None = None,
) -> dict:
    """Plan -> /plans/mapf request body (consecutive wait duplicates collapsed
    into departure semantics: the blockers on a waited-at node are kept).

    ``goal_actions`` is an optional list of VDA5050 action dicts attached to the
    last waypoint (the goal node) — e.g. ``[{"action_type": "jackUp"}]``.
    """
    profile = profiles[robot_id]
    waypoints = []
    for waypoint in plan.waypoints:
        blockers = [
            {"robot_id": b.name, "required_progress": b.required_progress}
            for b in waypoint.departure_blockers
        ]
        if waypoints and waypoints[-1]["name"] == waypoint.name:
            # wait step: same node again — merge its blockers, no new waypoint;
            # keep the later timestep as the node's progress.
            waypoints[-1]["departure_blockers"].extend(blockers)
            waypoints[-1]["progress"] = waypoint.progress
            continue
        waypoints.append(
            {
                "name": waypoint.name,
                "x": waypoint.position[0],
                "y": waypoint.position[1],
                # CBS timestep — what other robots' departure_blockers
                # (required_progress) compare against.
                "progress": waypoint.progress,
                "departure_blockers": blockers,
            }
        )

    if waypoints and goal_actions:
        waypoints[-1]["actions"] = goal_actions

    return {
        "robot_id": robot_id,
        "manufacturer": profile["manufacturer"],
        "serial_number": profile["serial"],
        "order_id": order_id,
        "map_id": map_id,
        "plan_version": plan_version,
        "task_id": task_id,
        "waypoints": waypoints,
    }


class PlannerService:
    def __init__(self) -> None:
        self.amqp_host = os.environ.get("AMQP_HOST", "amqp-broker")
        self.amqp_port = int(os.environ.get("AMQP_PORT", "5672"))
        self.master_url = os.environ.get(
            "MASTER_URL", "http://vda5050:8000"
        ).rstrip("/")

        # The VDA5050 master is the map/robots authority: fetch the planner grid
        # view and robot identities from it. Startup-fetch failures propagate and
        # are retried by main()'s loop (it catches OSError, which covers URLError).
        grid, self.map_id = self._fetch_grid()
        self.demo_mode = grid.get("mode", "dry_run")
        self.robot_profiles = self._fetch_robot_profiles()

        # A reachable-but-malformed grid (bad node id, missing start) would raise
        # KeyError/ValueError here; convert to a retryable ConnectionError so
        # main()'s loop retries (with backoff) instead of crash-looping.
        try:
            self.graph = MapGraph(grid)
        except (KeyError, ValueError, TypeError) as exc:
            raise ConnectionError(
                f"master /map/grid ({self.master_url}) returned a malformed grid: {exc}"
            ) from exc
        self.context = MultiAgentContext()
        self.coordinator = MAPFCoordinator(
            self.context, MapConstrainedCBSAdapter(self.graph)
        )
        self.plan_generator = PlanGenerator()

        # Dry-run: bootstrap from grid starts. Real demo: live /state only.
        self._initialise_all_agents()

        self.tasks: Dict[str, Task] = {}
        self.task_goal_actions: Dict[str, list] = {}
        self.plan_version = 0

        # TaskRequests arriving within this window are solved together in one
        # joint CBS pass. Without it, near-simultaneous requests (the
        # blue-ocean demo fires two) cause a solo v1 plan with no
        # departure_blockers to dispatch first — and the v2 plan that carries
        # the coordination can no longer replace the in-flight v1 order.
        self.batch_window_s = float(os.environ.get("PLANNER_BATCH_WINDOW_S", "0.7"))
        self.cbs_timeout_s = float(os.environ.get("PLANNER_CBS_TIMEOUT_S", "30"))
        # Pending (task_urn, robot_id) awaiting the next batch solve.
        self.pending_requests: list[tuple[str, str]] = []
        self.batch_timer_armed = False
        self._connection = None
        self._solve_in_progress = False
        self._solve_again = False
        self._cbs_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="mapf-cbs"
        )

    def _http_get_json(self, path: str) -> dict:
        url = f"{self.master_url}{path}"
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read())

    def _fetch_grid(self):
        """Planner topology from the master's /map/grid (node ids, undirected
        edges, blocked_edges, per-mode robot starts). The master is the single
        map authority — there is no baked fallback; a fetch failure raises a
        retryable ConnectionError that main()'s loop retries (depends_on keeps
        the master healthy before the planner starts)."""
        try:
            grid = self._http_get_json("/map/grid")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise ConnectionError(
                f"master /map/grid ({self.master_url}) unavailable: {exc}"
            ) from exc
        logger.info(
            "Fetched grid from %s/map/grid: %d nodes, mode=%s",
            self.master_url, len(grid.get("nodes", [])), grid.get("mode"),
        )
        return grid, grid.get("map_id", DEFAULT_MAP_ID)

    def _fetch_robot_profiles(self) -> Dict[str, dict]:
        """Robot identities {robot_id: {manufacturer, serial}} from the
        master's /robots (single source; no baked fallback — see _fetch_grid)."""
        try:
            data = self._http_get_json("/robots")
            profiles = {
                r["robot_id"]: {
                    "manufacturer": r["manufacturer"],
                    "serial": r["serial_number"],
                    # The master's /state reports poses under the same robot_id;
                    # kept here (as "fleet_id") for the live-pose lookup below.
                    "fleet_id": r["robot_id"],
                }
                for r in data["robots"]
            }
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            raise ConnectionError(
                f"master /robots ({self.master_url}) unavailable: {exc}"
            ) from exc
        logger.info(
            "Fetched %d robot profile(s) from %s/robots",
            len(profiles), self.master_url,
        )
        return profiles

    def _is_real_mode(self) -> bool:
        return self.demo_mode == "real"

    def _drop_task(self, robot_id: str) -> None:
        self.tasks.pop(robot_id, None)
        self.task_goal_actions.pop(robot_id, None)
        self.pending_requests = [
            item for item in self.pending_requests if item[1] != robot_id
        ]

    def _resolve_agent_start(
        self,
        robot_id: str,
        live_positions: Dict[str, str],
    ) -> str:
        """Agent start node: live /state in real mode; grid start fallback in dry-run."""
        profile = self.robot_profiles.get(robot_id, {})
        live = live_positions.get(profile.get("fleet_id", robot_id))
        if live:
            return live
        if self._is_real_mode():
            return ""
        return self.graph.robot_starts.get(robot_id, "")

    def _initialise_all_agents(self) -> None:
        live_positions = self._fetch_master_agv_positions()
        for robot_id in self.robot_profiles:
            start = self._resolve_agent_start(robot_id, live_positions)
            if start:
                self.context.initialise_agent(robot_id, start)
            elif self._is_real_mode():
                logger.warning(
                    "No live pose for %s at startup — agent not initialised "
                    "(is the adapter running and the robot localized?)",
                    robot_id,
                )

    def run(self) -> None:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.amqp_host, port=self.amqp_port)
        )
        self._connection = connection
        channel = connection.channel()
        channel.exchange_declare(
            exchange=AMQP_EXCHANGE, exchange_type="fanout", durable=True
        )
        channel.queue_declare(queue=PLANNER_QUEUE, durable=True)
        channel.queue_bind(queue=PLANNER_QUEUE, exchange=AMQP_EXCHANGE)
        channel.basic_consume(
            queue=PLANNER_QUEUE, on_message_callback=self.on_message, auto_ack=True
        )

        logger.info(
            "MAPF planner up: AMQP %s:%s queue %s, master %s, mode=%s, robots %s",
            self.amqp_host, self.amqp_port, PLANNER_QUEUE,
            self.master_url, self.demo_mode, list(self.robot_profiles),
        )
        channel.start_consuming()

    def on_message(self, channel, _method, _properties, body: bytes) -> None:
        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            return

        # The master emits TaskComplete when a robot's order finishes (§6.6.1),
        # letting us drop that robot from the joint-plan batch so a later solo
        # navigate isn't co-planned (and conflict-rejected) against a stale,
        # already-arrived task.
        if message.get("type") == "TaskComplete":
            try:
                self.handle_task_complete(message)
            except Exception:
                logger.exception("Failed to handle TaskComplete: %s", body)
            return

        if message.get("type") == "MapfReset":
            try:
                self.handle_mapf_reset(message)
            except Exception:
                logger.exception("Failed to handle MapfReset: %s", body)
            return

        if message.get("type") != "TaskRequest":
            return
        if message.get("taskType") != "amr_mapf":
            return
        if message.get("taskCommand", "START") != "START":
            return

        try:
            self.handle_task_request(channel, message)
        except Exception:
            logger.exception("Failed to handle TaskRequest: %s", body)

    def handle_task_complete(self, message: dict) -> None:
        """Drop a finished robot's task from the known-task batch.

        Only drops when the completed task_id matches the one we're holding —
        a newer task queued for the same robot after this completion must
        survive (avoids a stale completion wiping a fresh request)."""
        robot_id = message.get("robot_id", "")
        task_id = message.get("task_id", "")
        existing = self.tasks.get(robot_id)
        if existing is None:
            return
        if task_id and existing.task_id and existing.task_id != task_id:
            logger.info(
                "TaskComplete for %s task %s ignored; newer task %s pending",
                robot_id, task_id, existing.task_id,
            )
            return
        goal = existing.goal
        self.tasks.pop(robot_id, None)
        if goal:
            self.context.initialise_agent(robot_id, goal)
        logger.info(
            "TaskComplete: %s reached goal; dropped from batch (%d task(s) remain)",
            robot_id, len(self.tasks),
        )

    def _fetch_master_agv_positions(self) -> Dict[str, str]:
        """fleet_id -> last_node_id from the VDA5050 master /state.

        /state reports each AGV under its fleet_id (e.g. autoxing_1); callers
        map planner_id -> fleet_id via robot_profiles before looking up here."""
        url = f"{self.master_url}/state"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read())
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "master %s unreachable (%s); no live positions available",
                url,
                exc,
            )
            return {}
        return {
            agv["robot_id"]: agv["last_node_id"]
            for agv in data.get("agvs", [])
            if agv.get("robot_id") and agv.get("last_node_id")
        }

    def _abort_cbs_worker(self, reason: str = "") -> None:
        """Kill a hung CBS solve and recreate the single-thread executor."""
        logger.info(
            "Aborting CBS worker%s",
            f" ({reason})" if reason else "",
        )
        self._solve_in_progress = False
        self._solve_again = False
        self.pending_requests.clear()
        self.batch_timer_armed = False
        try:
            self._cbs_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            logger.exception("CBS executor shutdown failed")
        self._cbs_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="mapf-cbs"
        )

    def handle_mapf_reset(self, message: dict) -> None:
        """Drop batched tasks and sync agent positions from live /state (real mode)."""
        self._abort_cbs_worker(message.get("reason", "mapf_reset"))
        robot_id = message.get("robot_id")
        if robot_id:
            self._reset_robot_task(robot_id, message.get("reason", ""))
            return

        cleared_tasks = len(self.tasks)
        reason = message.get("reason", "")
        self.tasks.clear()
        self.pending_requests.clear()
        self.batch_timer_armed = False
        if hasattr(self.plan_generator, "plans_dict"):
            self.plan_generator.plans_dict.clear()

        live_positions = self._fetch_master_agv_positions()
        synced: Dict[str, str] = {}
        for rid, profile in self.robot_profiles.items():
            start = self._resolve_agent_start(rid, live_positions)
            if start:
                self.context.initialise_agent(rid, start)
                synced[rid] = start
            elif self._is_real_mode():
                logger.warning(
                    "MapfReset: no live pose for %s; agent position unchanged",
                    rid,
                )

        logger.info(
            "MapfReset (%s): cleared %d task(s); %d remain; synced live %s",
            reason,
            cleared_tasks,
            len(self.tasks),
            synced,
        )

    def _reset_robot_task(self, robot_id: str, reason: str) -> None:
        """Drop one robot's task from the planner batch and sync live pose."""
        had_task = robot_id in self.tasks
        self.tasks.pop(robot_id, None)
        self.task_goal_actions.pop(robot_id, None)
        self.pending_requests = [
            item for item in self.pending_requests if item[1] != robot_id
        ]
        if hasattr(self.plan_generator, "plans_dict"):
            self.plan_generator.plans_dict.pop(robot_id, None)

        live_positions = self._fetch_master_agv_positions()
        start = self._resolve_agent_start(robot_id, live_positions)
        if start:
            self.context.initialise_agent(robot_id, start)
        elif self._is_real_mode():
            logger.warning(
                "MapfReset: no live pose for %s; agent position unchanged",
                robot_id,
            )

        logger.info(
            "MapfReset (%s): dropped task for %s (had_task=%s); %d task(s) remain",
            reason,
            robot_id,
            had_task,
            len(self.tasks),
        )

    def handle_task_request(self, channel, message: dict) -> None:
        params = (message.get("taskParams") or [{}])[0]
        robot_id = params.get("robot_id", "")
        goal = params.get("goal_location", "")
        start = params.get("start_location", "")
        self.task_goal_actions[robot_id] = params.get("goal_actions", [])
        request_id = message.get("id", "")
        task_urn = request_id.removesuffix(":TaskRequest")

        if robot_id not in self.robot_profiles:
            logger.warning("Unknown robot_id %r; ignoring", robot_id)
            return

        # Set agent start from the request (live pose snapped by the scheduler).
        if start:
            self.context.initialise_agent(robot_id, start)

        self.tasks[robot_id] = Task(
            task_id=task_urn or f"{robot_id}_task", robot_id=robot_id, goal=goal
        )
        self.pending_requests.append((task_urn, robot_id))
        logger.info(
            "TaskRequest %s: %s -> %s (batched; %d task(s) known)",
            task_urn, robot_id, goal, len(self.tasks),
        )

        if not self.batch_timer_armed:
            self.batch_timer_armed = True
            channel.connection.call_later(self.batch_window_s, self.solve_batch)

    def solve_batch(self) -> None:
        """Schedule a joint CBS pass on a worker thread (keeps the I/O thread free)."""
        if self._solve_in_progress:
            self._solve_again = True
            return

        self.batch_timer_armed = False
        pending, self.pending_requests = self.pending_requests, []
        if not pending:
            return

        self._solve_in_progress = True
        threading.Thread(
            target=self._solve_batch_worker,
            args=(pending,),
            daemon=True,
            name="mapf-solve-batch",
        ).start()

    def _solve_batch_worker(self, pending: list[tuple[str, str]]) -> None:
        """CBS + HTTP on a worker thread; TaskStatus via a short-lived connection."""
        try:
            try:
                plans = self.replan()
            except Exception:
                logger.exception("Batch replan failed")
                plans = {}

            urn_by_robot = {robot_id: urn for urn, robot_id in pending}
            sent: Dict[str, bool] = {}
            for planned_robot, plan in plans.items():
                task_urn = urn_by_robot.get(planned_robot) or (
                    self.tasks[planned_robot].task_id
                    if planned_robot in self.tasks
                    else ""
                )
                sent[planned_robot] = self.post_plan(planned_robot, plan, task_urn)

            for task_urn, robot_id in pending:
                if sent.get(robot_id):
                    status = "COMPLETED"
                else:
                    status = "ERROR"
                    self._drop_task(robot_id)
                self.publish_task_status(task_urn, status)
        finally:
            self._solve_in_progress = False
            if self._solve_again:
                self._solve_again = False
                connection = self._connection
                if connection is not None and connection.is_open:
                    connection.add_callback_threadsafe(self._schedule_followup_solve)

    def _schedule_followup_solve(self) -> None:
        """Re-run solve_batch on the pika I/O thread after a coalesced batch."""
        if not self.pending_requests:
            return
        if not self.batch_timer_armed:
            self.batch_timer_armed = True
        self.solve_batch()

    def replan(self) -> Dict[str, object]:
        """Plan all known tasks together with the real MAPF stack."""
        # Sync every robot's live pose before CBS. Idle robots (no task this
        # batch) stay in the solve with start=goal=current node so CBS can plan
        # yield moves (step aside, then return) instead of treating them as fixed
        # obstacles — matching the original blue-ocean demo behaviour.
        live_positions = self._fetch_master_agv_positions()
        for robot_id in self.robot_profiles:
            start = self._resolve_agent_start(robot_id, live_positions)
            if start:
                self.context.initialise_agent(robot_id, start)
            elif self._is_real_mode():
                logger.warning(
                    "replan: no live pose for %s",
                    robot_id,
                )

        solver_plans = self._coordinator_solve_with_timeout(
            new_tasks=list(self.tasks.values()),
            committed_locations={},
            stationary_agents=set(),
            obstacles=[],
        )
        if not solver_plans:
            logger.error("Coordinator returned no plans for %s", self.tasks)
            return {}

        self.plan_version += 1
        plan_ids = {
            plan.agent_name: PlanId(uuid.uuid4(), self.plan_version)
            for plan in solver_plans
        }
        self.plan_generator.generate(solver_plans, plan_ids, None)
        plans = dict(self.plan_generator.plans_dict)

        for planned_robot, plan in plans.items():
            jsonable = plan_to_jsonable(planned_robot, plan)
            path = " -> ".join(w["name"] for w in jsonable["waypoints"])
            blocker_notes = [
                f"{w['name']} waits for {b['name']}@{b['required_progress']}"
                for w in jsonable["waypoints"]
                for b in w["departure_blockers"]
            ]
            logger.debug(
                "Plan v%d %s: %s (%d blockers%s)",
                self.plan_version,
                planned_robot,
                path,
                len(blocker_notes),
                f": {', '.join(blocker_notes)}" if blocker_notes else "",
            )
        return plans

    def _coordinator_solve_with_timeout(self, **kwargs):
        """Run CBS on a dedicated executor with a wall-clock timeout."""
        future = self._cbs_executor.submit(
            lambda: self.coordinator.solve(**kwargs)
        )
        try:
            return future.result(timeout=self.cbs_timeout_s)
        except FuturesTimeoutError:
            logger.error(
                "CBS timed out after %.0fs for tasks %s",
                self.cbs_timeout_s,
                self.tasks,
            )
            self._abort_cbs_worker("cbs_timeout")
            return []
        except (NoSolutionError, PlanningError) as exc:
            logger.error("CBS found no solution for tasks %s: %s", self.tasks, exc)
            return []

    def post_plan(self, robot_id: str, plan, task_urn: str) -> bool:
        """POST one robot's plan (coords + departure blockers) to the master."""
        order_id = f"mapf_{robot_id}_v{self.plan_version}_{uuid.uuid4().hex[:8]}"
        payload = plan_to_payload(
            robot_id, plan, order_id, self.map_id, self.plan_version, task_urn,
            self.robot_profiles,
            goal_actions=self.task_goal_actions.get(robot_id),
        )
        url = f"{self.master_url}/plans/mapf"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.loads(response.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            logger.error("Plan %s POST to %s failed: %s", order_id, url, exc)
            return False

        logger.info(
            "Plan %s -> %s (%s) accepted=%s dispatched=%s",
            order_id, url,
            " -> ".join(w["name"] for w in payload["waypoints"]),
            body.get("accepted"), body.get("dispatched"),
        )
        return True

    def publish_task_status(self, task_urn: str, status: str) -> None:
        """Publish TaskStatus on a short-lived connection (safe from worker threads)."""
        if not task_urn:
            return
        reply = {
            "type": "TaskStatus",
            "id": f"{task_urn}:TaskStatus",
            "taskType": "amr_mapf",
            "status": status,
            "taskExpectedStart": "",
            "taskExpectedEnd": "",
            "taskExpectedDuration": "",
        }
        body = json.dumps(reply)
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.amqp_host,
                    port=self.amqp_port,
                    socket_timeout=5.0,
                    blocked_connection_timeout=5.0,
                )
            )
        except (pika.exceptions.AMQPError, OSError) as exc:
            logger.error(
                "TaskStatus %s for %s not sent (AMQP unreachable): %s",
                status,
                task_urn,
                exc,
            )
            return
        try:
            channel = connection.channel()
            channel.exchange_declare(
                exchange=AMQP_EXCHANGE, exchange_type="fanout", durable=True
            )
            channel.basic_publish(
                exchange=AMQP_EXCHANGE, routing_key="", body=body
            )
            logger.info("TaskStatus %s for %s", status, task_urn)
        finally:
            connection.close()


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "DEBUG"),
        format="[%(levelname)s] %(asctime)s %(name)s: %(message)s",
    )
    logging.getLogger("pika").setLevel(logging.WARNING)

    retry_delay = 3.0
    while True:
        try:
            PlannerService().run()
        except KeyboardInterrupt:
            return 0
        except (pika.exceptions.AMQPError, ConnectionError, OSError) as exc:
            logger.warning(
                "Connection lost (%s); retrying in %.0fs", exc, retry_delay
            )
            time.sleep(retry_delay)


if __name__ == "__main__":
    raise SystemExit(main())
