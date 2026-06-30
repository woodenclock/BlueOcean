"""The shared adapter run loop, parametrized by a :class:`RobotAdapter`.

This is the single ``main()`` both demo adapters used to duplicate: parse args,
resolve identity + map_id from the master, build the MQTT protocol adapter, wire
``on_navigate`` onto a worker thread (so ``on_navigate`` returns fast and the C++
``suspend_for<NodeAckUpdate>`` can receive ``node_reached``), seed the pose, and
run until a signal.
"""

from __future__ import annotations

import argparse
import sys
import threading

import vda5050_core_py as vda

from adapter_core.identity import bootstrap_identity, resolve_map_id
from adapter_core.report import print_resolved_config
from adapter_core.robot import RobotAdapter


def _parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--disable-state-log",
        action="store_true",
        help="Suppress per-poll move_state=... lines while waiting for navigation.",
    )
    return parser.parse_args()


def run(robot: RobotAdapter, *, description: str | None = None) -> int:
    """Run ``robot`` as a VDA5050 adapter until a termination signal."""
    args = _parse_args(description or robot.__doc__ or "VDA5050 adapter client")
    robot.disable_state_log = args.disable_state_log
    config = robot.config

    # Identity comes from the master keyed by robot_id (manufacturer / serial /
    # client_id) — the only local inputs are ROBOT_ID + MASTER_URL.
    me = bootstrap_identity(config)
    # map_id is the master's active map — single source of truth.
    resolve_map_id(config)

    robot.prepare(me, args)
    print_resolved_config(
        config, me, endpoint_env=robot.endpoint_env, extra_lines=robot.config_extra_lines()
    )

    mqtt = vda.create_default_mqtt_client(config["broker"], config["client_id"])
    protocol = vda.ProtocolAdapter.make(
        mqtt,
        config["interface"],
        config["protocol_version"],
        config["manufacturer"],
        config["serial_number"],
    )
    adapter = vda.Adapter.make(protocol)
    nav = adapter.navigation_manager()

    robot.on_start(nav)

    def on_navigate(node: vda.Node) -> None:
        # Must return quickly — blocking work runs on a worker thread so the C++
        # suspend_for<NodeAckUpdate> can receive node_reached and advance.
        threading.Thread(
            target=robot.drive_to_node, args=(node, nav), daemon=True
        ).start()

    adapter.on_navigate(on_navigate)
    robot.seed_initial_pose(nav)
    robot.start_pose_stream(nav)
    adapter.start()
    print(
        f"Adapter started ({config['interface']}/v2/"
        f"{config['manufacturer']}/{config['serial_number']})",
        file=sys.stderr,
    )
    vda.run_until_signal(adapter)
    return 0
