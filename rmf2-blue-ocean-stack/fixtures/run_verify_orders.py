#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "paho-mqtt",
#     "pyyaml",
# ]
# ///
"""Subscribe to VDA5050 order topics and verify expected node sequences.

Run with uv (provisions paho-mqtt automatically): ``uv run fixtures/run_verify_orders.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("paho-mqtt missing — run with uv: uv run fixtures/run_verify_orders.py", file=sys.stderr)
    raise SystemExit(1)

import yaml

ROBOTS_YAML = Path(__file__).resolve().parent.parent / "maps" / "robots.yaml"

# Post-CBS resolved node sequences for the dry-run demo. Robots NOT listed here
# are still received and printed, just without a pass/fail assertion (so adding a
# robot to robots.yaml never breaks this script — fill in its sequence to assert).
EXPECTED_PATHS = {
    "autoxing-1": ["0,5", "1,5", "2,5", "3,5", "3,4"],
    "reeman-1": ["5,6", "5,5", "4,5", "3,5", "3,4", "4,4"],
}


def load_topic_map() -> dict[str, str]:
    """`uagv/v2/<Manufacturer>/<Serial>/order` -> robot_id, from robots.yaml."""
    data = yaml.safe_load(ROBOTS_YAML.read_text())
    topics: dict[str, str] = {}
    for r in data.get("robots", []):
        mfr, serial = r.get("manufacturer"), r.get("serial_number")
        rid = r.get("robot_id") or r.get("planner_id")
        if mfr and serial and rid:
            topics[f"uagv/v2/{mfr}/{serial}/order"] = rid
    return topics


TOPIC_TO_ROBOT = load_topic_map()


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
        default=list(TOPIC_TO_ROBOT.values()),
        help="Robots to wait for (default: all robot_ids in maps/robots.yaml)",
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
            expected = EXPECTED_PATHS.get(robot_id)
            actual = received.get(robot_id)
            if actual is None:
                print(f"FAIL {robot_id}: no order received")
                ok = False
                continue
            if expected is None:
                # No assertion configured for this robot — report only.
                print(f"INFO {robot_id}: {' -> '.join(actual)}  (no expected path set)")
            elif actual == expected:
                print(f"OK   {robot_id}: {' -> '.join(actual)}")
            else:
                print(f"FAIL {robot_id}: expected {' -> '.join(expected)}")
                print(f"       got      {' -> '.join(actual)}")
                ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
