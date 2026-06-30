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

"""Blue Ocean MAPF demo — the real res_mapf planning stack, no ROS.

Takes the two-robot tasks exactly as the task orchestrator sends them
(robot_id + goal grid node), plans with MAPFCoordinator + CBS constrained to
the demo map graph (maps/gametl_demo.lif.yaml allowed/blocked edges), and
prints the Plans we would hand to the VDA5050 master — including the
departure_blockers that sequence the shared 3,1 / 3,0 corridor.

Modeled on res_ros2/res_ros2/test/integration.py, but plan-server side only:
no transports, no executor, no pybullet.

    uv run --with rich python examples/blue_ocean_mapf_demo.py
"""

import json
import logging
import os
from dataclasses import asdict
from typing import Dict, List, Sequence, Tuple
from uuid import uuid4

import yaml
from res_mapf_planning.cbs.cbs import Environment, State
from res_mapf_planning.mapf_solve.solvers.cbs_adapter import CBSAdapter, _CBSOutput
from res_mapf_planning.planning.mapf_coordinator import MAPFCoordinator
from res_mapf_planning.planning.multi_agent_context import MultiAgentContext
from res_mapf_planning.traffic_dependencies.models.plan_id import PlanId
from res_mapf_planning.traffic_dependencies.plan_generator import PlanGenerator
from res_plan_server.models.task import Task
from rich.pretty import pprint

logger = logging.getLogger("blue_ocean_mapf_demo")

DEFAULT_MAP_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "maps", "gametl_demo.layout.yaml"
)
DEFAULT_ROBOTS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "maps", "robots.yaml"
)


def demo_robot_starts() -> "Dict[str, str]":
    """Dry-run robot starts for the standalone demo, from the canonical
    robots.yaml (the layout no longer carries a robots block; in the stack the
    planner gets starts from the master's /map/grid instead)."""
    with open(os.environ.get("ROBOTS_FILE", DEFAULT_ROBOTS_FILE), encoding="utf-8") as h:
        robots = yaml.safe_load(h)["robots"]
    return {
        (r.get("robot_id") or r.get("planner_id")): r["routes"]["dry_run"]["start"]
        for r in robots
    }

# Coordinates as the task orchestrator sends them (GoToNode taskParams):
# robot_id + goal_location. Starts come from robot onboarding (the layout map).
ORCHESTRATOR_TASKS = (
    {"robot_id": "autoxing-1", "task_id": "autoxing-1_goto", "goal": "3,4"},
    {"robot_id": "reeman-1", "task_id": "reeman-1_goto", "goal": "4,4"},
)


class MapGraph:
    """Allowed-edge graph (blocked edges removed) from the canonical layout.

    Accepts either a path to a layout YAML (``nodes`` as an id->spec mapping —
    the standalone demo's offline fallback) or a parsed grid view dict from the
    VDA5050 master's ``/map/grid`` (``nodes`` as an id list, plus ``robots``
    with per-mode starts). The integer grid is derived by parsing the "col,row"
    node ids, so no separate ``grid`` field is needed.
    """

    def __init__(self, source) -> None:
        data = self._load(source)

        node_ids = self._node_ids(data)
        self.nodes: set[Tuple[int, int]] = {self._parse(nid) for nid in node_ids}

        blocked = {frozenset(edge) for edge in data.get("blocked_edges", [])}
        self.moves: set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()
        for a, b in data.get("edges", []):
            if frozenset((a, b)) in blocked:
                continue
            node_a, node_b = self._parse(a), self._parse(b)
            self.moves.add((node_a, node_b))
            self.moves.add((node_b, node_a))

        self.dimension = [
            max(x for x, _ in self.nodes) + 1,
            max(y for _, y in self.nodes) + 1,
        ]
        self.robot_starts: Dict[str, str] = {
            robot_id: spec["start"]
            for robot_id, spec in data.get("robots", {}).items()
        }

    @staticmethod
    def _load(source) -> dict:
        if isinstance(source, dict):
            return source
        with open(source, encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    @staticmethod
    def _node_ids(data: dict) -> list:
        nodes = data.get("nodes", [])
        # Layout file: {id: {x, y, ...}}; grid view from /map/grid: [id, ...].
        return list(nodes.keys()) if isinstance(nodes, dict) else list(nodes)

    @staticmethod
    def _parse(node_id: str) -> Tuple[int, int]:
        x, y = node_id.split(",")
        return (int(x), int(y))


class MapConstrainedEnvironment(Environment):
    """CBS environment restricted to the map graph instead of an open grid."""

    def __init__(self, graph: MapGraph, agents, obstacles) -> None:
        self._graph = graph
        super().__init__(graph.dimension, agents, obstacles)

    def state_valid(self, state: State) -> bool:
        if (state.location.x, state.location.y) not in self._graph.nodes:
            return False
        return super().state_valid(state)

    def transition_valid(self, state_1: State, state_2: State) -> bool:
        move = (
            (state_1.location.x, state_1.location.y),
            (state_2.location.x, state_2.location.y),
        )
        if move not in self._graph.moves:
            return False
        return super().transition_valid(state_1, state_2)


class MapConstrainedCBSAdapter(CBSAdapter):
    """CBSAdapter solving on the map graph (drop-in MAPFSolverBase)."""

    def __init__(self, graph: MapGraph) -> None:
        self._graph = graph

    def _solve_cbs(self, dimension, agents, obstacles) -> _CBSOutput:
        from res_mapf_planning.cbs.cbs import CBS
        from res_mapf_planning.mapf_solve.exceptions import NoSolutionError

        env = MapConstrainedEnvironment(self._graph, agents, obstacles)
        solution = CBS(env).search()
        if not solution:
            raise NoSolutionError("CBS could not find a valid solution")
        return {"schedule": solution, "cost": env.compute_solution_cost(solution)}


def plan_to_jsonable(robot_id: str, plan) -> dict:
    """Plan dataclass -> JSON-safe dict (UUID PlanIds stringified)."""
    data = asdict(plan)
    data["robot_id"] = robot_id
    data["plan_id"] = str(plan.plan_id)
    for waypoint in data["waypoints"]:
        for blocker in waypoint["departure_blockers"]:
            blocker["plan_id"] = str(
                PlanId(
                    destination_session=blocker["plan_id"]["destination_session"],
                    plan_version=blocker["plan_id"]["plan_version"],
                )
            )
    return data


def main() -> int:
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(levelname)s] %(asctime)s %(name)s: %(message)s",
    )

    map_file = os.environ.get("MAP_FILE", DEFAULT_MAP_FILE)
    graph = MapGraph(map_file)
    logger.info(
        "Map graph: %d nodes, %d directed moves, dimension %s",
        len(graph.nodes), len(graph.moves), graph.dimension,
    )

    # Real plan-server stack: context + coordinator + CBS + plan generator.
    context = MultiAgentContext()
    coordinator = MAPFCoordinator(context, MapConstrainedCBSAdapter(graph))
    plan_generator = PlanGenerator()

    # Robot onboarding: starts from the layout's robots block if present, else
    # the canonical robots.yaml (dry-run routes).
    starts = graph.robot_starts or demo_robot_starts()
    for robot_id, start in starts.items():
        context.initialise_agent(robot_id, start)

    tasks: List[Task] = [
        Task(task_id=t["task_id"], robot_id=t["robot_id"], goal=t["goal"])
        for t in ORCHESTRATOR_TASKS
    ]
    logger.info("Solving MAPF for tasks: %s", tasks)

    solver_plans = coordinator.solve(
        new_tasks=tasks,
        committed_locations={},
        stationary_agents=set(),
        obstacles=[],
    )
    if not solver_plans:
        logger.error("Coordinator returned no plans")
        return 1

    session = uuid4()
    plan_ids = {plan.agent_name: PlanId(session, 1) for plan in solver_plans}
    plans = plan_generator.generate(solver_plans, plan_ids, None)

    blockers_total = 0
    for robot_id, plan in plan_generator.plans_dict.items():
        jsonable = plan_to_jsonable(robot_id, plan)
        blockers = sum(len(w["departure_blockers"]) for w in jsonable["waypoints"])
        blockers_total += blockers
        logger.debug(
            "Plan for %s (-> VDA5050 master), %d waypoints, %d departure_blockers:\n%s",
            robot_id,
            len(jsonable["waypoints"]),
            blockers,
            json.dumps(jsonable, indent=2),
        )
        pprint(jsonable, expand_all=True)

    logger.info(
        "Planned %d robots, %d departure_blockers total", len(plans), blockers_total
    )
    if blockers_total == 0:
        logger.warning(
            "No departure_blockers generated — expected some on the shared "
            "3,1 / 3,0 corridor; check the map constraints"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
