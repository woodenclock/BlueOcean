"""Per-node drive pipeline: plan → (orient) → drive, then ack node_reached."""

from __future__ import annotations

import math
import sys
import traceback
from collections.abc import Callable

import vda5050_core_py as vda

from adapter_core.node_ack import ack_cancelled_node
from autoxing.actions import execute_node_actions
from autoxing.bridge import (
    dispatch_move,
    plan_node_move,
    read_pose_xytheta,
    rotate_in_place_to,
    wait_for_arrival,
)


def _make_pose_mirror(
    nav: vda.NavigationManager, *, disable_state_log: bool
) -> "Callable[[vda.AGVPosition, str | None], None]":
    """Build the per-poll callback that mirrors pose into the published State."""
    def mirror_pose(agv: vda.AGVPosition, move_state: str | None) -> None:
        if agv.position_initialized:
            nav.set_agv_position(agv)
        if move_state and not disable_state_log:
            print(f"  move_state={move_state}", file=sys.stderr)

    return mirror_pose


def drive_to_node(
    node: vda.Node,
    nav: vda.NavigationManager,
    *,
    config: dict,
    disable_state_log: bool,
    is_last_node: bool,
) -> None:
    """Blocking Autoxing navigate + poll; calls node_reached on the worker thread.

    Per-node pipeline:
      1. PLAN   — one pose read decides orient-vs-coast (see ``plan_node_move``).
      2. ORIENT — at a corner only, rotate in place to face the path first so the
                  robot tracks the grid line instead of arcing off it.
      3. DRIVE  — coast through gentle, non-final waypoints (report reached within
                  the arrival radius, no full stop) or wait for a precise stop at
                  corners and the final node.
    """
    nav_timeout = config["nav_timeout"]
    poll_interval = config["poll_interval"]
    orient_before_move = config["orient_before_move"]
    orient_angle_rad = config["orient_angle_rad"]
    orient_theta_tol = config["orient_theta_tol"]
    pass_through_enabled = config["pass_through"]
    pass_through_dev = config["pass_through_dev"]
    try:
        pos = node.node_position
        print(
            f"Navigate to {node.node_id} ({pos.x}, {pos.y}) map={pos.map_id!r}",
            file=sys.stderr,
        )
        nav.set_driving(True)

        map_id = pos.map_id or ""
        mirror_pose = _make_pose_mirror(nav, disable_state_log=disable_state_log)

        # 1. PLAN — read the pose once and decide how to drive this node.
        plan = None
        pose0 = read_pose_xytheta(timeout=poll_interval + 1.0)
        if pose0 is not None:
            cur_x, cur_y, cur_theta = pose0
            plan = plan_node_move(
                cur_x,
                cur_y,
                cur_theta,
                pos.x,
                pos.y,
                is_last_node=is_last_node,
                allowed_deviation_xy=pos.allowed_deviation_x_y,
                orient_angle_rad=orient_angle_rad,
                default_dev_m=pass_through_dev,
            )
            print(
                f"  [plan] turn={math.degrees(plan.turn_rad):+.0f}° "
                f"orient={plan.needs_orient} pass_through={plan.pass_through} "
                f"tol={plan.arrival_tol_m:.2f}m last={is_last_node}",
                file=sys.stderr,
            )
        else:
            print(
                "  [plan] no pose — full-stop drive (no orient, no pass-through)",
                file=sys.stderr,
            )

        # 2. ORIENT — corner only: turn in place to face the path before driving.
        if plan is not None and orient_before_move and plan.needs_orient:
            rotate_in_place_to(
                plan.heading_rad,
                x=cur_x,
                y=cur_y,
                cur_theta=cur_theta,
                map_id=map_id,
                theta_tol_rad=orient_theta_tol,
                timeout_s=nav_timeout,
                poll_interval_s=poll_interval,
                on_poll=mirror_pose,
            )

        # 3. DRIVE — coast through gentle waypoints; full-stop otherwise. A node
        # carrying actions (jackUp/jackDown) always stops so the action runs while
        # stationary.
        coast = bool(
            plan and pass_through_enabled and plan.pass_through and not node.actions
        )
        move = dispatch_move(node, include_theta=not coast)
        if move is None:
            nav.set_driving(False)
            raise RuntimeError(f"Autoxing navigate failed for node {node.node_id}")

        move_id = move.get("id")
        print(f"  move id={move_id}{' (coast)' if coast else ''}", file=sys.stderr)

        terminal = wait_for_arrival(
            pos.x,
            pos.y,
            move_id=move_id,
            map_id=map_id,
            reach_radius_m=plan.arrival_tol_m if coast else None,
            timeout_s=nav_timeout,
            poll_interval_s=poll_interval,
            on_poll=mirror_pose,
        )

        nav.set_driving(False)
        if terminal == "cancelled":
            ack_cancelled_node(node, nav)
            return
        if terminal not in ("succeeded", "reached"):
            raise RuntimeError(f"Move to {node.node_id} ended with state {terminal!r}")

        execute_node_actions(node, nav)
        print(f"  node_reached({node.node_id})", file=sys.stderr)
        nav.node_reached(node)
    except Exception as exc:
        nav.set_driving(False)
        print(f"Navigation failed for {node.node_id}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
