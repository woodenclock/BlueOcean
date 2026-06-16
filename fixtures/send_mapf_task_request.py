#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pika",
# ]
# ///
"""Publish a demo amr_mapf TaskRequest to RabbitMQ @RECEIVE@ for bridge testing.

Run with uv (provisions pika automatically): ``uv run fixtures/send_mapf_task_request.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

try:
    import pika
except ImportError:
    print("pika missing — run with uv: uv run fixtures/send_mapf_task_request.py", file=sys.stderr)
    raise SystemExit(1)


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
        "--robot-id",
        default="autoxing",
        choices=("autoxing", "reeman"),
        help="Robot to send the task for",
    )
    parser.add_argument(
        "--goal",
        default=None,
        help="Goal grid node (default: robot default from gametl_demo.lif.yaml)",
    )
    parser.add_argument("--task-id", default=None, help="Optional fixed task UUID")
    args = parser.parse_args()

    default_goals = {"autoxing": "3,0", "reeman": "4,0"}
    goal = args.goal or default_goals[args.robot_id]
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
