#!/usr/bin/env python3

"""Sample WebSocket `/planning_state` for ~15s — MOVING vs IDLE heuristic."""

from __future__ import annotations

from collections import Counter

from credentials import CONSTANTS as ROBOT

from ws_helper import ws_poll_topic


def check_robot_movement(*, duration_sec: float = 15.0) -> str:
    msgs = ws_poll_topic(ROBOT.ROBOT_IP, "/planning_state", duration_sec=duration_sec)
    if not msgs:
        return "NO_DATA"

    states = [m.get("move_state") for m in msgs if isinstance(m, dict)]
    ctr = Counter(s for s in states if isinstance(s, str))

    stuck = False
    for m in msgs:
        if isinstance(m, dict) and m.get("stuck_state"):
            stuck = stuck or True

    if ctr.get("moving", 0) > 2:
        return "MOVING" + ("_STUCK_HINT" if stuck else "")
    if ctr.get("moving", 0) > 0:
        return "MOVING_MINOR"
    terminal = ctr.get("succeeded", 0) + ctr.get("failed", 0) + ctr.get("cancelled", 0)
    if ctr.get("idle", 0) > 3 and terminal:
        return "IDLE_TERMINAL_RECENT"

    dominant = ctr.most_common(1)[0][0] if ctr else "UNKNOWN"

    stuck_note = "_STUCK" if stuck else ""
    return dominant + stuck_note


if __name__ == "__main__":
    print("Watching /planning_state for ~15s …")
    label = check_robot_movement()
    print(label)
