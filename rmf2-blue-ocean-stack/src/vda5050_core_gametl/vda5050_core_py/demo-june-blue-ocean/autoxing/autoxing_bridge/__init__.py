"""Autoxing L300 bridge — spellbook REST/WS helpers for VDA5050 adapter clients."""

from __future__ import annotations

from typing import Any

__all__ = [
    "CREATOR",
    "DEFAULT_AT_GOAL_TOL_M",
    "DEFAULT_MIN_ORIENT_DIST_M",
    "DEFAULT_ORIENT_ANGLE_RAD",
    "DEFAULT_PASS_THROUGH_DEV_M",
    "DEFAULT_POLL_INTERVAL_S",
    "DEFAULT_THETA_TOL_RAD",
    "NavPlan",
    "PLANNING_TOPIC",
    "TERMINAL_MOVE_STATES",
    "TRACKED_POSE_TOPIC",
    "angle_diff",
    "at_goal",
    "dispatch_move",
    "dispatch_rotate",
    "distance_to_target",
    "move_state_from_status",
    "plan_node_move",
    "poll_pose_and_planning",
    "read_pose_xytheta",
    "rotate_in_place_to",
    "stream_tracked_pose",
    "tracked_pose_to_agv_position",
    "wait_for_arrival",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import bridge

    return getattr(bridge, name)
