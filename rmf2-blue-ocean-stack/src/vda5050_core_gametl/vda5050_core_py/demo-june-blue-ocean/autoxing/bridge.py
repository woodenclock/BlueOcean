"""Autoxing bridge imports — the robot REST/WebSocket I/O this adapter drives.

Importing the autoxing_bridge package runs its ``ensure_spellbook()``, which puts the
spellbook dir on ``sys.path`` — so ``jack_up`` / ``jack_down`` are importable
right after. A missing spellbook raises here (real-robot operation is the only
mode), which is the intended hard failure.
"""

from __future__ import annotations

from autoxing.autoxing_bridge import (
    dispatch_move,
    plan_node_move,
    poll_pose_and_planning,
    read_pose_xytheta,
    rotate_in_place_to,
    stream_tracked_pose,
    tracked_pose_to_agv_position,
    wait_for_arrival,
)
from jack_down import jack_down
from jack_up import jack_up

__all__ = [
    "dispatch_move",
    "plan_node_move",
    "poll_pose_and_planning",
    "read_pose_xytheta",
    "rotate_in_place_to",
    "stream_tracked_pose",
    "tracked_pose_to_agv_position",
    "wait_for_arrival",
    "jack_up",
    "jack_down",
]
