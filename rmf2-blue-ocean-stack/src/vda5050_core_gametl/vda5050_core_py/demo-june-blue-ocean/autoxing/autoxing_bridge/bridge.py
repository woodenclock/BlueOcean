"""Shared Autoxing API layer for GameTL VDA5050 integration."""

from __future__ import annotations

import asyncio
import math
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ._spellbook_path import ensure_spellbook

ensure_spellbook()

from credentials import CONSTANTS as ROBOT  # noqa: E402
from credentials import timeout_seconds  # noqa: E402
from get_move_status import get_move_status  # noqa: E402
from navigate import navigate, planning_move_state  # noqa: E402
# _ws_stream_topics is the spellbook's long-lived subscribe loop (the engine
# behind the `ws_topic`/`get_pose` stream CLIs). The public ws_stream_topics
# wrapper installs SIGINT/stdin watchers that only work on the main thread, so
# the background pose-stream thread drives this inner coroutine directly.
from ws_helper import _ws_stream_topics, ws_get_topics  # noqa: E402

import vda5050_core_py as vda

CREATOR = "vda5050_autoxing_l300"
TRACKED_POSE_TOPIC = "/tracked_pose"
PLANNING_TOPIC = "/planning_state"
TERMINAL_MOVE_STATES = frozenset({"succeeded", "failed", "cancelled"})
DEFAULT_POLL_INTERVAL_S = 0.5
DEFAULT_AT_GOAL_TOL_M = 0.15

# ── Orient / pass-through tuning ───────────────────────────────────────────────
# We turn in place only for real corners and let the robot fly through gentle
# waypoints. Two independent thresholds drive that:
#   * DEFAULT_ORIENT_ANGLE_RAD — decision threshold. If the heading the robot must
#     turn to face the next node exceeds this, it's a corner → rotate in place
#     first. Below it the path is "straight enough" → just drive.
#   * DEFAULT_THETA_TOL_RAD — precision of the in-place rotation itself; the turn
#     is considered done once the heading is within this band.
# DEFAULT_MIN_ORIENT_DIST_M guards the bearing maths: closer than this to the
# target the bearing is ill-defined, so orientation is skipped.
# DEFAULT_PASS_THROUGH_DEV_M is the fallback arrival radius for pass-through nodes
# when the order doesn't carry an allowedDeviationXY.
DEFAULT_ORIENT_ANGLE_RAD = math.radians(45.0)
DEFAULT_THETA_TOL_RAD = 0.05
DEFAULT_MIN_ORIENT_DIST_M = 0.20
DEFAULT_PASS_THROUGH_DEV_M = 0.25


def dispatch_move(
    node: vda.Node,
    *,
    target_accuracy: float | None = None,
    include_theta: bool = True,
) -> dict | None:
    """Map VDA5050 node → POST /chassis/moves (spellbook navigate).

    Forwards ``nodePosition.theta`` when the order carries it. Unset (null) is
    preserved — it is not coerced to 0; navigate omits target_ori when null.

    ``include_theta=False`` drops the target heading entirely — used for
    pass-through waypoints, where settling to a final orientation would defeat
    the point of coasting through without stopping.
    """
    pos = node.node_position
    theta = pos.theta if include_theta else None
    return navigate(
        pos.x,
        pos.y,
        theta,
        creator=CREATOR,
        target_accuracy=target_accuracy,
    )


# ── Navigation geometry & per-node planning ───────────────────────────────────


def angle_diff(a: float, b: float) -> float:
    """Smallest signed difference ``a - b`` wrapped to [-pi, pi] (radians)."""
    return (a - b + math.pi) % (2.0 * math.pi) - math.pi


def read_pose_xytheta(
    robot_ip: str | None = None,
    *,
    timeout: float | None = None,
) -> tuple[float, float, float] | None:
    """One-shot read of the robot pose as ``(x, y, theta)`` or ``None``.

    ``None`` when the robot isn't localized / no pose frame arrives in time.
    """
    pose, _planning = poll_pose_and_planning(robot_ip=robot_ip, timeout=timeout)
    pos = pose.get("pos") if isinstance(pose, dict) else None
    ori = pose.get("ori") if isinstance(pose, dict) else None
    if not (isinstance(pos, (list, tuple)) and len(pos) >= 2) or ori is None:
        return None
    return float(pos[0]), float(pos[1]), float(ori)


@dataclass(frozen=True)
class NavPlan:
    """How a single node should be driven, decided up front from one pose read.

    ``turn_rad`` is the signed turn from the current heading to the bearing toward
    the node. ``needs_orient`` and ``pass_through`` are mutually exclusive
    outcomes (a node is either a corner we stop+turn for, or a waypoint we coast
    through) — except the final node, which always gets a full stop.
    """

    heading_rad: float          # bearing from the current pose to the node
    turn_rad: float             # signed turn the robot must make to face it
    needs_orient: bool          # |turn| over the corner threshold → rotate first
    pass_through: bool          # coast through within arrival_tol instead of stopping
    arrival_tol_m: float        # radius that counts as "reached" for pass-through


def plan_node_move(
    cur_x: float,
    cur_y: float,
    cur_theta: float,
    target_x: float,
    target_y: float,
    *,
    is_last_node: bool,
    allowed_deviation_xy: float | None,
    orient_angle_rad: float = DEFAULT_ORIENT_ANGLE_RAD,
    min_orient_dist_m: float = DEFAULT_MIN_ORIENT_DIST_M,
    default_dev_m: float = DEFAULT_PASS_THROUGH_DEV_M,
) -> NavPlan:
    """Decide orient-vs-coast for one node from the current pose.

    Rules (matching the demo intent):
      * Corner (``|turn| > orient_angle_rad``) → orient in place first, full stop.
      * Gentle turn AND not the last node → pass through within the arrival radius
        so the robot doesn't brake to a stop only to accelerate again.
      * Last node (or a too-close target where the bearing is unreliable) → full
        stop, no orient.
    """
    heading = math.atan2(target_y - cur_y, target_x - cur_x)
    turn = angle_diff(heading, cur_theta)

    # Too close to read a meaningful bearing → don't orient, don't coast.
    if math.hypot(target_x - cur_x, target_y - cur_y) < min_orient_dist_m:
        needs_orient = False
        pass_through = False
    else:
        needs_orient = abs(turn) > orient_angle_rad
        pass_through = (not needs_orient) and (not is_last_node)

    tol = allowed_deviation_xy if allowed_deviation_xy is not None else default_dev_m
    return NavPlan(
        heading_rad=heading,
        turn_rad=turn,
        needs_orient=needs_orient,
        pass_through=pass_through,
        arrival_tol_m=float(tol),
    )


# ── In-place rotation (orient phase) ───────────────────────────────────────────


def dispatch_rotate(
    target_ori: float,
    *,
    x: float,
    y: float,
    target_accuracy: float | None = None,
) -> dict | None:
    """POST /chassis/moves — in-place rotation to ``target_ori`` at (x, y).

    Sends the robot's current XY as the target with ``inplace_rotate`` so the
    planner turns on the spot instead of driving an arc to reach the heading.
    """
    return navigate(
        x,
        y,
        target_ori,
        creator=CREATOR,
        target_accuracy=target_accuracy,
        inplace_rotate=True,
    )


def rotate_in_place_to(
    heading_rad: float,
    *,
    x: float,
    y: float,
    cur_theta: float,
    robot_ip: str | None = None,
    map_id: str = "",
    theta_tol_rad: float = DEFAULT_THETA_TOL_RAD,
    timeout_s: float | None = None,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    on_poll: Callable[[vda.AGVPosition, str | None], None] | None = None,
) -> None:
    """Turn in place to ``heading_rad`` and block until theta matches.

    One send: the current point (x, y) with orientation on (``inplace_rotate``).
    The wait loop only reads pose/state — it never re-posts the move. Returns once
    the heading is within ``theta_tol_rad`` (or the rotate move reports
    ``succeeded``); raises on a failed/cancelled move or timeout.
    """
    print(f"  [orient] rotating in place to heading {heading_rad:.3f} rad", file=sys.stderr)
    rot = dispatch_rotate(heading_rad, x=x, y=y)
    if rot is None:
        raise RuntimeError("orient: in-place rotate dispatch failed")
    move_id = rot.get("id")

    timeout = timeout_s if timeout_s is not None else timeout_seconds()
    deadline = time.monotonic() + timeout
    # Reuse the pose already read for the first theta check instead of polling it
    # again back-to-back; each iteration then polls once after the sleep.
    latest_theta: float | None = cur_theta
    move_state: str | None = None
    while time.monotonic() < deadline:
        # Heading match is the real success signal — return as soon as theta is
        # within tolerance, even before the move reports a terminal state.
        if latest_theta is not None and abs(angle_diff(heading_rad, latest_theta)) <= theta_tol_rad:
            print(f"  [orient] heading matched ({latest_theta:.3f} rad)", file=sys.stderr)
            return
        if move_state in ("failed", "cancelled"):
            raise RuntimeError(f"orient: rotate ended with state {move_state!r}")
        if move_state == "succeeded":
            return

        time.sleep(poll_interval_s)

        move_state = (
            move_state_from_status(get_move_status(int(move_id)))
            if move_id is not None
            else None
        )
        pose_msg, planning_msg = poll_pose_and_planning(
            robot_ip=robot_ip, timeout=poll_interval_s + 1.0
        )
        if move_state is None and planning_msg is not None:
            move_state = planning_move_state(planning_msg)
        agv = tracked_pose_to_agv_position(pose_msg, map_id=map_id)
        if on_poll is not None:
            on_poll(agv, move_state)
        latest_theta = (
            float(pose_msg["ori"])
            if isinstance(pose_msg, dict) and pose_msg.get("ori") is not None
            else None
        )

    raise TimeoutError(
        f"orient: timed out after {timeout:.0f}s aligning to heading "
        f"{heading_rad:.3f} rad."
    )


def poll_pose_and_planning(
    robot_ip: str | None = None,
    *,
    timeout: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """One-shot WS poll of /tracked_pose and /planning_state."""
    ip = robot_ip or ROBOT.ROBOT_IP
    try:
        got = ws_get_topics(
            ip,
            [TRACKED_POSE_TOPIC, PLANNING_TOPIC],
            timeout=timeout,
        )
    except TypeError:
        return None, None
    return got.get(TRACKED_POSE_TOPIC), got.get(PLANNING_TOPIC)


def move_state_from_status(status: dict[str, Any] | None) -> str | None:
    """Extract terminal move state from GET /chassis/moves/{id} response."""
    if not isinstance(status, dict):
        return None
    for key in ("state", "move_state", "status"):
        val = status.get(key)
        if isinstance(val, str):
            return val
    return None


def distance_to_target(
    pose: dict[str, Any] | None,
    target_x: float,
    target_y: float,
) -> float | None:
    """Euclidean distance from tracked pose to target XY (meters)."""
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
    """True when tracked pose is within ``tol_m`` of the target XY."""
    dist = distance_to_target(pose, target_x, target_y)
    return dist is not None and dist <= tol_m


def tracked_pose_to_agv_position(
    pose: dict[str, Any] | None,
    map_id: str = "",
) -> vda.AGVPosition:
    """Convert WS /tracked_pose payload to VDA5050 AGVPosition."""
    agv = vda.AGVPosition()
    agv.position_initialized = False
    agv.map_id = map_id
    if not isinstance(pose, dict):
        return agv

    pos = pose.get("pos")
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        agv.x = float(pos[0])
        agv.y = float(pos[1])
        agv.position_initialized = True

    ori = pose.get("ori")
    if ori is not None:
        agv.theta = float(ori)

    return agv


def stream_tracked_pose(
    on_pose: Callable[[vda.AGVPosition], None],
    *,
    robot_ip: str | None = None,
    map_id: str = "",
    stop_event: Any | None = None,
    reconnect_delay_s: float = 2.0,
) -> None:
    """Continuously mirror WS ``/tracked_pose`` into ``on_pose`` (blocking).

    Unlike :func:`poll_pose_and_planning` (a one-shot read) this holds a single
    subscription open and invokes ``on_pose`` on every pose publish — so the
    adapter keeps publishing a fresh ``agvPosition`` even when the robot is idle
    with no active move. Intended to run on a daemon thread.

    Reconnects after ``reconnect_delay_s`` if the socket drops, until
    ``stop_event`` (anything with ``.is_set()``, e.g. ``threading.Event``) is
    set. Only initialized poses are forwarded, so a transient non-localized
    frame never clobbers a good published position.
    """
    ip = robot_ip or ROBOT.ROBOT_IP

    def _stopped() -> bool:
        return stop_event is not None and stop_event.is_set()

    def _handle(data: Any) -> None:
        agv = tracked_pose_to_agv_position(data, map_id=map_id)
        if agv.position_initialized:
            on_pose(agv)

    async def _run() -> None:
        aio_stop = asyncio.Event()

        async def _bridge_stop() -> None:
            # Poll the (thread-owned) stop_event into this loop's asyncio.Event
            # so a blocking ws recv() unwinds promptly on shutdown.
            while not _stopped():
                await asyncio.sleep(0.25)
            aio_stop.set()

        watcher = asyncio.create_task(_bridge_stop()) if stop_event is not None else None
        try:
            while not _stopped():
                try:
                    await _ws_stream_topics(
                        ip,
                        [TRACKED_POSE_TOPIC],
                        max_messages=None,
                        use_topic_list=True,
                        stop_event=aio_stop,
                        on_message=_handle,
                    )
                except Exception as exc:  # noqa: BLE001 — keep the stream alive
                    print(
                        f"Pose stream dropped ({exc}); reconnecting in "
                        f"{reconnect_delay_s:.0f}s",
                        file=sys.stderr,
                    )
                if _stopped():
                    break
                await asyncio.sleep(reconnect_delay_s)
        finally:
            aio_stop.set()
            if watcher is not None:
                await watcher

    asyncio.run(_run())


def wait_for_arrival(
    target_x: float,
    target_y: float,
    *,
    move_id: int | None = None,
    robot_ip: str | None = None,
    map_id: str = "",
    reach_radius_m: float | None = None,
    timeout_s: float | None = None,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    on_poll: Callable[[vda.AGVPosition, str | None], None] | None = None,
) -> str:
    """
    Poll until the node is reached, then return the move state.

    Two completion modes:
      * Full stop (``reach_radius_m`` is None) — wait for a terminal move_state
        (succeeded|failed|cancelled). This is the precise stop at corners and at
        the final node.
      * Pass-through (``reach_radius_m`` set) — return ``"reached"`` as soon as the
        pose is within that radius of the target, WITHOUT cancelling the in-flight
        move. The next node's move then supersedes it, so the robot coasts through
        the waypoint instead of braking to a perfect stop. A terminal state still
        ends the wait early.

    Uses GET /chassis/moves/{id} when ``move_id`` is set (REST, no websockets).
    Also tries WS /tracked_pose for VDA5050 position mirroring when available.
    """
    timeout = timeout_s if timeout_s is not None else timeout_seconds()
    deadline = time.monotonic() + timeout
    last_state: str | None = None

    while time.monotonic() < deadline:
        move_state: str | None = None
        if move_id is not None:
            move_state = move_state_from_status(get_move_status(int(move_id)))

        pose_msg, planning_msg = poll_pose_and_planning(
            robot_ip=robot_ip, timeout=poll_interval_s + 1.0
        )
        if move_state is None and planning_msg is not None:
            move_state = planning_move_state(planning_msg)

        agv = tracked_pose_to_agv_position(pose_msg, map_id=map_id)
        if move_state is not None:
            last_state = move_state

        if on_poll is not None:
            on_poll(agv, move_state)

        # A terminal state always ends the wait, in either mode.
        if move_state in TERMINAL_MOVE_STATES:
            return move_state

        # Pass-through: "reached" the moment we're inside the arrival radius.
        if reach_radius_m is not None and at_goal(pose_msg, target_x, target_y, tol_m=reach_radius_m):
            return "reached"

        time.sleep(poll_interval_s)

    raise TimeoutError(
        f"Timed out after {timeout:.0f}s waiting for terminal move_state "
        f"(last={last_state!r}, target=({target_x}, {target_y}))."
    )
