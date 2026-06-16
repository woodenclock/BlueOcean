#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pika",
# ]
# ///
"""Publish a demo Schedule payload to the RabbitMQ @RECEIVE@ fanout exchange.

Run with uv (provisions pika automatically): ``uv run fixtures/send_schedule.py``.
"""

import argparse
import json
import os
import sys

try:
    import pika
except ImportError:
    print("pika missing — run with uv: uv run fixtures/send_schedule.py", file=sys.stderr)
    sys.exit(1)

SCHEDULE_PAYLOAD = {
    "type": "Schedule",
    "id": "workflow-run-demo-001",
    "payload": {
        "version": "0.1.0",
        "start": "node_1",
        "ops": {
            "node_1": {
                "type": "node",
                "builder": "MQTTDeviceReqNode",
                "config": {
                    "asset_id": "MANIP1",
                    "task_id": "Depalletize001",
                    "task_type": "Depalletize",
                    "area_id": "Outgoing1",
                },
                "next": "node_2",
            },
            "node_2": {
                "type": "node",
                "builder": "MQTTDeviceReqNode",
                "config": {
                    "asset_id": "SNS1",
                    "task_id": "Store001",
                    "task_type": "Store",
                    "area_id": "Incoming1",
                },
                "next": {"builtin": "terminate"},
            },
        },
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Send demo Schedule to task orchestrator via AMQP")
    parser.add_argument("--host", default="localhost", help="RabbitMQ host (default: localhost)")
    default_amqp_port = int(os.environ.get("AMQP_PORT", "5672"))
    parser.add_argument(
        "--port",
        type=int,
        default=default_amqp_port,
        help=f"RabbitMQ AMQP port (default: {default_amqp_port}, from AMQP_PORT env)",
    )
    args = parser.parse_args()

    params = pika.ConnectionParameters(host=args.host, port=args.port)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.exchange_declare(exchange="@RECEIVE@", exchange_type="fanout", durable=True)

    body = json.dumps(SCHEDULE_PAYLOAD)
    channel.basic_publish(exchange="@RECEIVE@", routing_key="", body=body)
    print(f"Published Schedule to @RECEIVE@ on {args.host}:{args.port}")
    print(json.dumps(SCHEDULE_PAYLOAD, indent=2))

    connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
