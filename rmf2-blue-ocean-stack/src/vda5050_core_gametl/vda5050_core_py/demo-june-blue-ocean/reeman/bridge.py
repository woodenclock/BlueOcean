"""Reeman bridge imports — the robot REST I/O this adapter drives.

Importing the reeman_bridge package runs its ``ensure_spellbook()``; a missing spellbook
raises here (real-robot operation is the only mode), the intended hard failure.
"""

from __future__ import annotations

from reeman.reeman_bridge import (
    dispatch_move,
    poll_pose_and_planning,
    poll_pose_stream,
    tracked_pose_to_agv_position,
    wait_for_arrival,
)

__all__ = [
    "dispatch_move",
    "poll_pose_and_planning",
    "poll_pose_stream",
    "tracked_pose_to_agv_position",
    "wait_for_arrival",
]
