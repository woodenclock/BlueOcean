#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "paho-mqtt",
# ]
# ///
"""Subscribe to VDA5050 order topics and verify expected node sequences.

Run with uv (provisions paho-mqtt automatically): ``uv run fixtures/verify_orders.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("paho-mqtt missing — run with uv: uv run fixtures/verify_orders.py", file=sys.stderr)
    raise SystemExit(1)


EXPECTED_PATHS = {
    "autoxing": ["0,1", "1,1", "2,1", "3,1", "3,0"],
    "reeman": ["5,2", "5,1", "4,1", "3,1", "3,0", "4,0"],
}

TOPIC_TO_ROBOT = {
    "uagv/v2/Autoxing/A001/order": "autoxing",
    "uagv/v2/Reeman/R001/order": "reeman",
}


def node_sequence(order: dict) -> list[str]:
    nodes = sorted(order.get("nodes", []), key=lambda item: item.get("sequenceId", 0))
    return [str(node.get("nodeId")) for node in nodes]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    default_mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
    parser.add_argument(
        "--port",
        type=int,
        default=default_mqtt_port,
        help=f"MQTT broker port (default: {default_mqtt_port}, from MQTT_PORT env)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for orders",
    )
    parser.add_argument(
        "--robots",
        nargs="*",
        default=["autoxing", "reeman"],
        help="Robots to wait for",
    )
    args = parser.parse_args()

    received: dict[str, list[str]] = {}
    lock = threading.Lock()
    done = threading.Event()

    def on_message(
        _client: mqtt.Client,
        _userdata: object,
        message: mqtt.MQTTMessage,
    ) -> None:
        robot_id = TOPIC_TO_ROBOT.get(message.topic)
        if robot_id is None:
            return
        try:
            order = json.loads(message.payload.decode("utf-8"))
        except json.JSONDecodeError:
            return

        sequence = node_sequence(order)
        with lock:
            received[robot_id] = sequence
            if all(robot in received for robot in args.robots):
                done.set()

    client_kwargs: dict = {"client_id": "verify-orders"}
    if hasattr(mqtt, "CallbackAPIVersion"):
        client_kwargs["callback_api_version"] = mqtt.CallbackAPIVersion.VERSION2
    client = mqtt.Client(**client_kwargs)
    client.on_message = on_message
    client.connect(args.host, args.port, keepalive=60)
    client.subscribe("uagv/v2/+/+/order")
    client.loop_start()

    print(f"Waiting up to {args.timeout}s for orders from: {', '.join(args.robots)}")
    done.wait(timeout=args.timeout)
    client.loop_stop()
    client.disconnect()

    ok = True
    with lock:
        for robot_id in args.robots:
            expected = EXPECTED_PATHS[robot_id]
            actual = received.get(robot_id)
            if actual is None:
                print(f"FAIL {robot_id}: no order received")
                ok = False
                continue
            if actual == expected:
                print(f"OK   {robot_id}: {' -> '.join(actual)}")
            else:
                print(f"FAIL {robot_id}: expected {' -> '.join(expected)}")
                print(f"       got      {' -> '.join(actual)}")
                ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
