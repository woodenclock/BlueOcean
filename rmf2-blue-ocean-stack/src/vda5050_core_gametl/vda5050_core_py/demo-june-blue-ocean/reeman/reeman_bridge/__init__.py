"""Reeman bridge — spellbook REST helpers for VDA5050 adapter clients."""

from __future__ import annotations

from typing import Any

__all__ = [
    "CREATOR",
    "DEFAULT_AT_GOAL_TOL_M",
    "DEFAULT_POLL_INTERVAL_S",
    "TERMINAL_MOVE_STATES",
    "at_goal",
    "dispatch_move",
    "distance_to_target",
    "move_state_from_status",
    "poll_pose_and_planning",
    "poll_pose_stream",
    "tracked_pose_to_agv_position",
    "wait_for_arrival",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import bridge

    return getattr(bridge, name)
