#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pika",
#     "pyyaml",
# ]
# ///
"""Publish a demo amr_mapf TaskRequest to RabbitMQ @RECEIVE@ for bridge testing.

Run with uv (provisions pika automatically): ``uv run fixtures/run_send_mapf_task_request.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

try:
    import pika
except ImportError:
    print("pika missing — run with uv: uv run fixtures/run_send_mapf_task_request.py", file=sys.stderr)
    raise SystemExit(1)

import yaml

ROBOTS_YAML = Path(__file__).resolve().parent.parent / "maps" / "robots.yaml"


def load_robots(mode: str = "dry_run") -> dict[str, str]:
    """robot_id -> goal node for `mode`, read from the canonical robots.yaml
    so this script tracks the fleet automatically (no hardcoded robot list)."""
    data = yaml.safe_load(ROBOTS_YAML.read_text())
    goals: dict[str, str] = {}
    for r in data.get("robots", []):
        rid = r.get("robot_id") or r.get("planner_id")
        if not rid:
            continue
        goals[rid] = (r.get("routes", {}).get(mode, {}) or {}).get("goal", "")
    return goals


def build_payload(
    robot_id: str,
    goal_location: str,
    task_id: str | None = None,
) -> dict:
    task_uuid = task_id or str(uuid.uuid4())
    return {
        "type": "TaskRequest",
        "id": f"urn:ngsi-ld:Task:{task_uuid}:TaskRequest",
        "taskType": "amr_mapf",
        "taskCommand": "START",
        "taskParams": [
            {
                "goal_location": goal_location,
                "robot_id": robot_id,
            }
        ],
        "taskExpectedStart": "",
        "taskExpectedEnd": "",
        "taskExpectedDuration": "",
    }


def main() -> int:
    # Peek at --mode so --robot-id choices come from robots.yaml (single parse pass).
    mode_parser = argparse.ArgumentParser(add_help=False)
    mode_parser.add_argument(
        "--mode",
        default="dry_run",
        choices=("dry_run", "real"),
    )
    mode_args, _ = mode_parser.parse_known_args()
    goals = load_robots(mode_args.mode)
    robot_ids = tuple(goals)
    default_robot = robot_ids[0] if robot_ids else None

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="RabbitMQ host")
    default_amqp_port = int(os.environ.get("AMQP_PORT", "5672"))
    parser.add_argument(
        "--port",
        type=int,
        default=default_amqp_port,
        help=f"RabbitMQ AMQP port (default: {default_amqp_port}, from AMQP_PORT env)",
    )
    parser.add_argument(
        "--mode",
        default="dry_run",
        choices=("dry_run", "real"),
        help="Which routes.<mode> goal to default to (from robots.yaml)",
    )
    if robot_ids:
        parser.add_argument(
            "--robot-id",
            default=default_robot,
            choices=robot_ids,
            help="Robot to send the task for (from robots.yaml robot_ids)",
        )
    else:
        parser.add_argument(
            "--robot-id",
            required=True,
            help="Robot to send the task for (from robots.yaml robot_ids)",
        )
    parser.add_argument(
        "--goal",
        default=None,
        help="Goal grid node (default: robot's routes goal from maps/robots.yaml)",
    )
    parser.add_argument("--task-id", default=None, help="Optional fixed task UUID")
    args = parser.parse_args()

    goals = load_robots(args.mode)
    goal = args.goal or goals.get(args.robot_id, "")
    payload = build_payload(args.robot_id, goal, args.task_id)

    params = pika.ConnectionParameters(host=args.host, port=args.port)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange="@RECEIVE@", exchange_type="fanout", durable=True)
    channel.basic_publish(
        exchange="@RECEIVE@",
        routing_key="",
        body=json.dumps(payload),
    )
    print(f"Published amr_mapf TaskRequest to @RECEIVE@ on {args.host}:{args.port}")
    print(json.dumps(payload, indent=2))
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
