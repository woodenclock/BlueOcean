#!/usr/bin/env python3
"""AutoxingAdapter — vda5050_core_py Adapter + Autoxing REST/WebSocket I/O.

Implements diagram steps ⑤–⑨: on_navigate → POST /chassis/moves → poll pose/status
→ set_agv_position/set_driving → node_reached. Node iteration stays in C++.

AutoXing is itself the master reference frame, so poses need no transform.
``nodePosition.mapId`` must use the active map's ``map_name`` (e.g. "From Mapping
40"); the map must already be loaded on the robot.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import threading

import vda5050_core_py as vda

import adapter_core
from adapter_core.config import base_config
from adapter_core.identity import export_endpoint
from adapter_core.robot import RobotAdapter
from autoxing import drive
from autoxing.bridge import (
    poll_pose_and_planning,
    stream_tracked_pose,
    tracked_pose_to_agv_position,
)
from autoxing.calibration import log_master_map_and_check_calibration
from order_tracker import OrderTracker


def _autoxing_config() -> dict:
    config = base_config(
        default_client_id="autoxing_l300_agv",
        default_manufacturer="Autoxing",
        default_serial="A001",
    )
    config.update(
        {
            # Orient-along-path: at a corner (heading to the next node differs from
            # the current heading by more than ORIENT_ANGLE_DEG) rotate in place to
            # face the path before driving. On by default; ORIENT_BEFORE_MOVE=0 to
            # always drive straight in.
            "orient_before_move": os.environ.get("ORIENT_BEFORE_MOVE", "1") != "0",
            "orient_angle_rad": math.radians(float(os.environ.get("ORIENT_ANGLE_DEG", "45"))),
            "orient_theta_tol": float(os.environ.get("ORIENT_THETA_TOL_RAD", "0.05")),
            # Pass-through: on a gentle, non-final node, count it reached as soon as
            # the robot is within allowedDeviationXY (this fallback when unset) so it
            # coasts through instead of braking. On by default; PASS_THROUGH=0 to
            # always full-stop.
            "pass_through": os.environ.get("PASS_THROUGH", "1") != "0",
            "pass_through_dev": float(os.environ.get("PASS_THROUGH_DEV_M", "0.25")),
        }
    )
    return config


class AutoxingAdapter(RobotAdapter):
    """Autoxing L300 adapter (master-frame; no robot↔master transform)."""

    endpoint_env = "AUTOXING_BASE_URL"

    def __init__(self) -> None:
        super().__init__()
        self.config = _autoxing_config()
        self.order_tracker: OrderTracker | None = None

    def prepare(self, me: dict, args: argparse.Namespace) -> None:
        export_endpoint(
            me,
            self.config,
            env_var="AUTOXING_BASE_URL",
            fallback_desc=(
                "the bridge will fall back to its CONSTANTS.yml / spellbook host, "
                "which may be the WRONG robot."
            ),
        )
        try:
            from ensure_onboard_map import ensure_autoxing_onboard_map  # noqa: PLC0415

            ensure_autoxing_onboard_map(
                self.config["manufacturer"], self.config["serial_number"]
            )
        except Exception as exc:  # noqa: BLE001 — best-effort startup
            print(f"Onboard map ensure skipped: {exc}", file=sys.stderr)
        log_master_map_and_check_calibration()

    def config_extra_lines(self) -> list[str]:
        return ["  transform     : master frame (AutoXing is the reference frame)"]

    def on_start(self, nav: vda.NavigationManager) -> None:
        # Track the live VDA5050 order off the broker so drive_to_node knows which
        # node is the order's final one (which must be a precise stop, never
        # coasted through). Best-effort: a broker hiccup just defaults every node
        # to a full stop. See order_tracker.py.
        self.order_tracker = OrderTracker(
            broker=self.config["broker"],
            interface=self.config["interface"],
            protocol_version=self.config["protocol_version"],
            manufacturer=self.config["manufacturer"],
            serial_number=self.config["serial_number"],
            client_id=self.config["client_id"],
        )
        self.order_tracker.start()

    def seed_initial_pose(self, nav: vda.NavigationManager) -> None:
        """Poll the robot's pose once and seed the published State's agvPosition.

        A master (or the demo publisher) needs an initialized pose up front to make
        the first order node trivially reachable (VDA5050 §6.6.3.1). Best-effort.
        """
        map_id = self.config["map_id"]
        try:
            pose_msg, _planning = poll_pose_and_planning()
            agv = tracked_pose_to_agv_position(pose_msg, map_id=map_id)
            if agv.position_initialized:
                nav.set_agv_position(agv)
                print(f"Initial pose seeded: ({agv.x}, {agv.y}) map={map_id!r}", file=sys.stderr)
            else:
                print("Initial pose unavailable (not localized?)", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — best-effort startup seed
            print(f"Initial pose poll failed: {exc}", file=sys.stderr)

    def start_pose_stream(self, nav: vda.NavigationManager) -> None:
        """Hold a WS ``/tracked_pose`` subscription open and mirror every publish,
        so an idle robot's published agvPosition never goes stale."""
        map_id = self.config["map_id"]

        def _on_pose(agv: vda.AGVPosition) -> None:
            nav.set_agv_position(agv)

        thread = threading.Thread(
            target=stream_tracked_pose,
            args=(_on_pose,),
            kwargs={"map_id": map_id},
            daemon=True,
            name="pose-stream",
        )
        thread.start()
        print("Live pose stream started (WS /tracked_pose).", file=sys.stderr)

    def drive_to_node(self, node: vda.Node, nav: vda.NavigationManager) -> None:
        # Coast through a node only when we positively know it is NOT the final
        # node; unknown (no order captured yet) defaults to a full stop.
        last_id = self.order_tracker.last_node_id() if self.order_tracker else None
        is_last = last_id is None or node.node_id == last_id
        drive.drive_to_node(
            node,
            nav,
            config=self.config,
            disable_state_log=self.disable_state_log,
            is_last_node=is_last,
        )


def main() -> int:
    return adapter_core.run(AutoxingAdapter(), description=__doc__)


if __name__ == "__main__":
    sys.exit(main())
