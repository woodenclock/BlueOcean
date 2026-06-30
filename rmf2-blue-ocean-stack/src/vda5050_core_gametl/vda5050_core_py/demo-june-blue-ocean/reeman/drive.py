"""Per-node Reeman drive: tf-convert target, dispatch, poll to arrival, ack."""

from __future__ import annotations

import os
import sys
import threading
import traceback

import vda5050_core_py as vda

from adapter_core.node_ack import ack_cancelled_node
from reeman.bridge import dispatch_move, wait_for_arrival
from reeman.transform import set_master_position

# Rack docking nodes need a turn-in-place-then-drive-straight approach when listed
# in REEMAN_ALIGN_NODES (semicolon-separated, since node ids contain commas —
# e.g. "2,4;3,4").
_ALIGN_NODE_IDS = frozenset(
    s.strip() for s in os.environ.get("REEMAN_ALIGN_NODES", "").split(";") if s.strip()
)


def is_rack_approach(node: vda.Node) -> bool:
    """True when ``node`` should be reached with the aligned two-phase approach."""
    return node.node_id in _ALIGN_NODE_IDS


def drive_to_node(
    node: vda.Node,
    nav: vda.NavigationManager,
    *,
    config: dict,
    tf,
    disable_state_log: bool,
    pause_event: threading.Event,
) -> None:
    """Blocking Reeman navigate + poll; calls node_reached on the worker thread.

    Order coordinates are master-frame (AutoXing); ``tf`` converts them into the
    Reeman frame for dispatch and converts mirrored poses back for publishing.
    With ``tf=None`` (no valid calibration) navigation is blocked.
    """
    map_id = config["map_id"]
    nav_timeout = config["nav_timeout"]
    poll_interval = config["poll_interval"]
    try:
        pos = node.node_position
        print(
            f"Navigate to {node.node_id} ({pos.x}, {pos.y}) map={pos.map_id!r}",
            file=sys.stderr,
        )

        if tf is None:
            raise RuntimeError(
                "navigation blocked: no valid Reeman→AutoXing transform "
                "(AutoXing offline at init and no usable calibration cache)"
            )

        nav.set_driving(True)
        aligned = is_rack_approach(node)
        if aligned:
            print(
                f"  rack approach: turn-in-place then drive straight into {node.node_id}",
                file=sys.stderr,
            )
        move = dispatch_move(node, to_robot=tf.to_robot, aligned=aligned)
        if move is None:
            nav.set_driving(False)
            raise RuntimeError(f"Reeman navigate failed for node {node.node_id}")

        move_id = move.get("id")
        if move_id is not None:
            print(f"  move id={move_id}", file=sys.stderr)

        def mirror_pose(agv: vda.AGVPosition, move_state: str | None) -> None:
            if agv.position_initialized:
                set_master_position(nav, agv, map_id)
            if move_state and not disable_state_log:
                print(f"  move_state={move_state}", file=sys.stderr)

        # wait_for_arrival's at-goal check compares against the raw robot pose, so
        # the target must be in the Reeman frame.
        robot_x, robot_y, _ = tf.to_robot(pos.x, pos.y, pos.theta)
        pause_event.set()
        try:
            terminal = wait_for_arrival(
                robot_x,
                robot_y,
                move_id=move_id,
                map_id=map_id,
                timeout_s=nav_timeout,
                poll_interval_s=poll_interval,
                on_poll=mirror_pose,
                pose_to_master=tf.to_master,
            )
        finally:
            pause_event.clear()

        nav.set_driving(False)
        if terminal == "cancelled":
            ack_cancelled_node(node, nav)
            return
        if terminal != "succeeded":
            raise RuntimeError(f"Move to {node.node_id} ended with state {terminal!r}")

        print(f"  node_reached({node.node_id})", file=sys.stderr)
        nav.node_reached(node)
    except Exception as exc:
        nav.set_driving(False)
        print(f"Navigation failed for {node.node_id}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
