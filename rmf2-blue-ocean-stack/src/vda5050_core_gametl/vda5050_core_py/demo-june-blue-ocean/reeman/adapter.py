#!/usr/bin/env python3
"""ReemanAdapter — vda5050_core_py Adapter + Reeman spellbook REST I/O.

VDA5050 adapter for Reeman/R001 (and same-make instances, e.g. reeman-2-blue).
Uses ``reeman_bridge`` (spellbook REST: POST /cmd/nav, GET /reeman/pose, GET
/reeman/nav_status). Poses are published in the master (AutoXing) frame via the
/transform calibration; without a valid transform, navigation is blocked.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading

import vda5050_core_py as vda

import adapter_core
from adapter_core.config import base_config
from adapter_core.identity import export_endpoint
from adapter_core.robot import RobotAdapter
from reeman import drive
from reeman.bridge import (
    poll_pose_and_planning,
    poll_pose_stream,
    tracked_pose_to_agv_position,
)
from reeman.transform import (
    MasterFrameTransform,
    load_tf_from_master,
    set_master_position,
)


class ReemanAdapter(RobotAdapter):
    """Reeman adapter; publishes in the master frame via a /transform similarity."""

    endpoint_env = "REEMAN_ROBOT_IP"

    def __init__(self) -> None:
        super().__init__()
        self.config = base_config(
            default_client_id="reeman_r001_agv",
            default_manufacturer="Reeman",
            default_serial="R001",
        )
        self.tf: MasterFrameTransform | None = None
        # While drive_to_node polls pose, pause the live-pose stream so both loops
        # don't hammer /reeman/pose concurrently.
        self._pose_stream_pause = threading.Event()

    def prepare(self, me: dict, args: argparse.Namespace) -> None:
        export_endpoint(
            me,
            self.config,
            env_var="REEMAN_ROBOT_IP",
            fallback_desc=(
                "reeman_bridge will fall back to CONSTANTS.yml's active robot, "
                "which may be the WRONG robot (e.g. another Reeman instance)."
            ),
        )
        try:
            from ensure_onboard_map import ensure_reeman_onboard_map  # noqa: PLC0415

            ensure_reeman_onboard_map(
                self.config["manufacturer"], self.config["serial_number"]
            )
        except Exception as exc:  # noqa: BLE001 — best-effort startup
            print(f"Onboard map ensure skipped: {exc}", file=sys.stderr)
        # Transform key = this robot's own robot_id (its adapters.<robot_id>
        # entry); MAP_TF_ADAPTER overrides.
        self.tf = load_tf_from_master(
            os.environ.get("MAP_TF_ADAPTER") or self.config["robot_id"]
        )
        if self.tf is None:
            print(
                "WARNING: starting without a map transform — orders will be "
                "rejected until calibration succeeds (restart with AutoXing "
                "online, or ensure master /transform is available).",
                file=sys.stderr,
            )

    def config_extra_lines(self) -> list[str]:
        tf = self.tf
        tf_desc = "NONE — navigation blocked" if tf is None else getattr(tf, "source", "?")
        lines = [f"  transform     : {tf_desc}"]
        if isinstance(tf, MasterFrameTransform):
            lines.append(
                f"    tx={tf.tx:.4f} ty={tf.ty:.4f} theta={tf.theta:.6f} "
                f"scale={tf.scale:.6f}   <- master /transform"
            )
        return lines

    def seed_initial_pose(self, nav: vda.NavigationManager) -> None:
        """Poll the robot once and seed agvPosition (master frame via tf). Skipped
        with no valid transform — a robot-frame pose under the master map_id would
        be a lie. Best-effort."""
        if self.tf is None:
            print("Initial pose seed skipped: no valid Reeman→AutoXing transform.",
                  file=sys.stderr)
            return
        map_id = self.config["map_id"]
        try:
            pose_msg, _planning = poll_pose_and_planning()
            agv = tracked_pose_to_agv_position(
                pose_msg, map_id=map_id, to_master=self.tf.to_master
            )
            if agv.position_initialized:
                set_master_position(nav, agv, map_id)
                print(f"Initial pose seeded: ({agv.x}, {agv.y}) map={map_id!r}", file=sys.stderr)
            else:
                print("Initial pose unavailable (not localized?)", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — best-effort startup seed
            print(f"Initial pose poll failed: {exc}", file=sys.stderr)

    def start_pose_stream(self, nav: vda.NavigationManager) -> None:
        """Poll REST ``/reeman/pose`` continuously and mirror every read (master
        frame via tf), so an idle robot's agvPosition never goes stale. Only with
        a valid transform."""
        if self.tf is None:
            return
        map_id = self.config["map_id"]

        def _on_pose(agv: vda.AGVPosition) -> None:
            set_master_position(nav, agv, map_id)

        thread = threading.Thread(
            target=poll_pose_stream,
            args=(_on_pose,),
            kwargs={
                "map_id": map_id,
                "to_master": self.tf.to_master,
                "pause_event": self._pose_stream_pause,
            },
            daemon=True,
            name="pose-stream",
        )
        thread.start()
        print("Live pose stream started (REST /reeman/pose poll).", file=sys.stderr)

    def drive_to_node(self, node: vda.Node, nav: vda.NavigationManager) -> None:
        drive.drive_to_node(
            node,
            nav,
            config=self.config,
            tf=self.tf,
            disable_state_log=self.disable_state_log,
            pause_event=self._pose_stream_pause,
        )


def main() -> int:
    return adapter_core.run(ReemanAdapter(), description=__doc__)


if __name__ == "__main__":
    sys.exit(main())
