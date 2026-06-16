#!/usr/bin/env python3
"""POST a two-robot MAPF schedule to the RMF2 Scheduler API.

This writes a schedule into the Scheduler via:

    POST /schedule/edit/batch?dry_run=false

It intentionally mirrors the scheduler examples under
src/rmf2_scheduler_gametl/rmf2_scheduler_server_py/script/, but avoids importing
repo packages so it can run from the umbrella repo root.

Current limitation: the scheduler server still needs a ProcessExecutor/task
executor wired before these stored tasks will automatically become orchestrator
GoToNode workflows.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import uuid4


DEFAULT_TASKS = (
    {
        "robot_id": "autoxing",
        "start": "0,1",
        "goal": "3,0",
    },
    {
        "robot_id": "reeman",
        "start": "5,2",
        "goal": "4,0",
    },
)


def iso_timestamp(delay_seconds: int) -> str:
    timestamp = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    return timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def task_action(robot_id: str, goal: str, start_time: str) -> tuple[str, dict]:
    task_id = str(uuid4())
    task = {
        "id": task_id,
        "type": "custom/go_to_amr",
        "start_time": start_time,
        "resource_id": robot_id,
        "task_details": {
            # Existing scheduler examples use "coordinates"; GoToNode maps it
            # to the AMQP task_params goal_location.
            "coordinates": goal,
            "goal_location": goal,
            "robot_id": robot_id,
            "task_type": "amr_mapf",
        },
    }
    return task_id, {"type": "TASK_ADD", "task": task}


def build_schedule_actions(start_delay_seconds: int = 30) -> list[dict]:
    start_time = iso_timestamp(start_delay_seconds)
    process_id = str(uuid4())

    task_ids: list[str] = []
    actions: list[dict] = []
    for item in DEFAULT_TASKS:
        task_id, action = task_action(item["robot_id"], item["goal"], start_time)
        task_ids.append(task_id)
        actions.append(action)

    # No dependencies: both GoTo tasks are intended to be planned together.
    actions.append(
        {
            "type": "PROCESS_ADD",
            "process": {
                "id": process_id,
                "graph": [{"id": task_id, "needs": []} for task_id in task_ids],
                "process_details": {
                    "name": "two_robot_mapf_demo",
                    "map": "maps/gametl_demo.lif.yaml",
                    "robots": DEFAULT_TASKS,
                },
            },
        }
    )
    return actions


def post_schedule(url: str, actions: list[dict], dry_run: bool) -> tuple[int, str]:
    query = urllib.parse.urlencode({"dry_run": str(dry_run).lower()})
    target = f"{url}?{query}"
    body = json.dumps(actions).encode("utf-8")
    request = urllib.request.Request(
        target,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to connect to Scheduler at {url}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="Scheduler host")
    default_scheduler_port = int(os.environ.get("SCHEDULER_PORT", "8089"))
    parser.add_argument(
        "--port",
        type=int,
        default=default_scheduler_port,
        help=f"Scheduler port (default: {default_scheduler_port}, from SCHEDULER_PORT env)",
    )
    parser.add_argument(
        "--start-delay",
        type=int,
        default=30,
        help="Seconds from now for both tasks to start",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate only")
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the generated batch edit JSON without posting",
    )
    args = parser.parse_args()

    actions = build_schedule_actions(args.start_delay)
    if args.print_only:
        print(json.dumps(actions, indent=2))
        return 0

    endpoint = f"http://{args.host}:{args.port}/schedule/edit/batch"
    print(f"POST {endpoint}?dry_run={str(args.dry_run).lower()}")
    status, text = post_schedule(endpoint, actions, args.dry_run)
    print(f"HTTP {status}")
    try:
        print(json.dumps(json.loads(text), indent=2))
    except json.JSONDecodeError:
        print(text)

    if 200 <= status < 300:
        print(
            "\nSchedule posted. Reminder: automatic execution still requires the "
            "scheduler task executor and AMQP->ROS bridge TODOs."
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
