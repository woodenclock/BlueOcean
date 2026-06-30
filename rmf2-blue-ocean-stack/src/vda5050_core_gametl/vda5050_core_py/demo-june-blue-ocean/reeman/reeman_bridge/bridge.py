"""Shared Reeman API layer for GameTL VDA5050 integration."""

from __future__ import annotations

import math
import sys
import time
from collections.abc import Callable
from typing import Any

from ._spellbook_path import ensure_spellbook

ensure_spellbook()

from credentials import timeout_seconds  # noqa: E402
from get_move_status import get_move_status  # noqa: E402
from get_pose import get_reeman_pose  # noqa: E402
from navigate import navigate, navigate_reeman_rotate_then_drive  # noqa: E402

import vda5050_core_py as vda

CREATOR = "vda5050_reeman_r001"
TERMINAL_MOVE_STATES = frozenset({"succeeded", "failed", "cancelled"})
DEFAULT_POLL_INTERVAL_S = 0.5
DEFAULT_AT_GOAL_TOL_M = 0.15


def _rest_poll_timeout(explicit: float | None = None) -> float:
    """REST read timeout — use spellbook ``timeout_seconds()`` (not poll interval)."""
    return explicit if explicit is not None else timeout_seconds()


def dispatch_move(
    node: vda.Node,
    *,
    target_accuracy: float | None = None,
    to_robot: Callable[[float, float, float | None], tuple[float, float, float | None]] | None = None,
    aligned: bool = False,
) -> dict | None:
    """Map VDA5050 node → POST /cmd/nav (spellbook navigate_reeman).

    ``to_robot`` converts the node's master-frame (AutoXing) coordinates into
    the Reeman map frame before dispatch; without it the coordinates are sent
    as-is.

    MAPF/UI orders are position-only (no ``nodePosition.theta``); spellbook
    ``navigate_reeman`` receives ``target_ori=None`` and computes heading toward
    the goal via ``atan2`` before ``POST /cmd/nav`` — same as dashboard direct
    control and the CLI ``navigate X Y`` command.

    With ``aligned=True`` (rack docking nodes) the move is split into an
    in-place rotation to face the target followed by a straight drive in, so
    the robot turns once at the approach node and arrives nose-in without
    hunting its heading at the rack (see ``navigate_reeman_rotate_then_drive``).
    """
    pos = node.node_position
    x, y = pos.x, pos.y
    if to_robot is not None:
        x, y, _ = to_robot(x, y, pos.theta)
    if aligned:
        return navigate_reeman_rotate_then_drive(x, y)
    return navigate(
        x,
        y,
        None,
        creator=CREATOR,
        target_accuracy=target_accuracy,
    )


def poll_pose_and_planning(
    robot_ip: str | None = None,
    *,
    timeout: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """One-shot REST poll of /reeman/pose (no planning topic on Reeman)."""
    del robot_ip  # active robot comes from credentials.CONSTANTS
    try:
        pose = get_reeman_pose(timeout=_rest_poll_timeout(timeout))
    except TypeError:
        return None, None
    return pose, None


def move_state_from_status(status: dict[str, Any] | None) -> str | None:
    """Extract move state from GET /reeman/nav_status normalized response."""
    if not isinstance(status, dict):
        return None
    for key in ("status", "state", "move_state"):
        val = status.get(key)
        if isinstance(val, str):
            return val
    return None


def distance_to_target(
    pose: dict[str, Any] | None,
    target_x: float,
    target_y: float,
) -> float | None:
    """Euclidean distance from pose to target XY (meters)."""
    if not isinstance(pose, dict):
        return None
    pos = pose.get("pos")
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        return None
    return math.hypot(float(pos[0]) - target_x, float(pos[1]) - target_y)


def at_goal(
    pose: dict[str, Any] | None,
    target_x: float,
    target_y: float,
    *,
    tol_m: float = DEFAULT_AT_GOAL_TOL_M,
) -> bool:
    """True when pose is within ``tol_m`` of the target XY."""
    dist = distance_to_target(pose, target_x, target_y)
    return dist is not None and dist <= tol_m


def tracked_pose_to_agv_position(
    pose: dict[str, Any] | None,
    map_id: str = "",
    to_master: Callable[[float, float, float | None], tuple[float, float, float | None]] | None = None,
) -> vda.AGVPosition:
    """Convert Reeman pose payload to VDA5050 AGVPosition.

    ``to_master`` converts the robot-frame pose into the master (AutoXing)
    frame so the published agvPosition is master-frame; ``map_id`` should
    then be the master map id.
    """
    agv = vda.AGVPosition()
    agv.position_initialized = False
    agv.map_id = map_id
    if not isinstance(pose, dict):
        return agv

    pos = pose.get("pos")
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        x, y = float(pos[0]), float(pos[1])
        ori = pose.get("ori")
        theta = float(ori) if ori is not None else None
        if to_master is not None:
            x, y, theta = to_master(x, y, theta)
        agv.x = x
        agv.y = y
        if theta is not None:
            agv.theta = theta
        agv.position_initialized = True

    return agv


def poll_pose_stream(
    on_pose: Callable[[vda.AGVPosition], None],
    *,
    map_id: str = "",
    to_master: Callable[[float, float, float | None], tuple[float, float, float | None]] | None = None,
    poll_interval_s: float = 1.0,
    stop_event: Any | None = None,
    pause_event: Any | None = None,
) -> None:
    """Continuously poll REST ``/reeman/pose`` and mirror into ``on_pose`` (blocking).

    Reeman FlyBoat uses REST ``GET /reeman/pose``; the live feed
    is a poll loop rather than a subscription. ``_publish_initial_pose`` seeds
    the pose once and ``_drive_to_node`` refreshes it only mid-move, so an idle
    robot's published ``agvPosition`` goes stale; this keeps it fresh the whole
    time the adapter is up, independent of navigation.

    ``to_master`` converts the robot-frame pose into the master (AutoXing) frame
    so the published position matches the master ``map_id``. Runs until
    ``stop_event`` (anything with ``.is_set()``) is set; intended for a daemon
    thread. Set ``pause_event`` while navigation owns pose polling (avoids
    duplicate concurrent REST calls). Only initialized poses are forwarded.
    """
    def _stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    def _paused() -> bool:
        return pause_event is not None and pause_event.is_set()

    while not _stopped():
        if _paused():
            time.sleep(poll_interval_s)
            continue
        try:
            pose_msg, _planning = poll_pose_and_planning()
            agv = tracked_pose_to_agv_position(
                pose_msg, map_id=map_id, to_master=to_master
            )
            if agv.position_initialized:
                on_pose(agv)
        except Exception as exc:  # noqa: BLE001 — keep the poll loop alive
            print(f"Pose poll failed: {exc}", file=sys.stderr)
        time.sleep(poll_interval_s)


def wait_for_arrival(
    target_x: float,
    target_y: float,
    *,
    move_id: int | None = None,
    robot_ip: str | None = None,
    map_id: str = "",
    timeout_s: float | None = None,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    on_poll: Callable[[vda.AGVPosition, str | None], None] | None = None,
    pose_to_master: Callable[[float, float, float | None], tuple[float, float, float | None]] | None = None,
) -> str:
    """
    Poll GET /reeman/nav_status until terminal status (succeeded|failed|cancelled).

    Reeman has no per-move id; ``move_id`` is ignored. Pose mirroring uses
    GET /reeman/pose each poll cycle.

    ``target_x``/``target_y`` are in the Reeman robot frame (the at-goal check
    compares them against the raw robot pose). ``pose_to_master`` converts the
    pose handed to ``on_poll`` into the master frame for publishing.
    """
    del move_id, robot_ip
    timeout = timeout_s if timeout_s is not None else timeout_seconds()
    deadline = time.monotonic() + timeout
    last_state: str | None = None
    seen_moving = False

    while time.monotonic() < deadline:
        status = get_move_status(0)
        move_state = move_state_from_status(status)

        pose_msg, _planning = poll_pose_and_planning()
        agv = tracked_pose_to_agv_position(
            pose_msg, map_id=map_id, to_master=pose_to_master
        )

        if move_state == "running":
            seen_moving = True

        if move_state == "running" and at_goal(pose_msg, target_x, target_y):
            move_state = "succeeded"

        # Reeman often reports res=4 (cancelled) once when a new POST /cmd/nav
        # replaces the previous goal — ignore terminal states until the move has
        # actually started (res=1 / running), same as monitor_reeman for res=3.
        if move_state in TERMINAL_MOVE_STATES and not seen_moving:
            if move_state == "succeeded" and at_goal(pose_msg, target_x, target_y):
                seen_moving = True
            else:
                move_state = None

        if move_state is not None:
            last_state = move_state

        if on_poll is not None:
            on_poll(agv, move_state)

        if move_state in TERMINAL_MOVE_STATES:
            return move_state

        time.sleep(poll_interval_s)

    raise TimeoutError(
        f"Timed out after {timeout:.0f}s waiting for terminal move_state "
        f"(last={last_state!r}, target=({target_x}, {target_y}))."
    )
