#!/usr/bin/env python3
"""Poll Reeman pose and nav status — GameTL diagram step ⑦."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from . import (
    DEFAULT_AT_GOAL_TOL_M,
    at_goal,
    distance_to_target,
    poll_pose_and_planning,
)
from api_client import print_json
from get_move_status import get_move_status


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-shot poll of /reeman/pose and /reeman/nav_status.",
    )
    parser.add_argument("--move-id", type=int, default=0, help="ignored; Reeman uses nav_status")
    parser.add_argument("--target-x", type=float, help="optional target X for at_goal check")
    parser.add_argument("--target-y", type=float, help="optional target Y for at_goal check")
    parser.add_argument(
        "--tol-m",
        type=float,
        default=DEFAULT_AT_GOAL_TOL_M,
        help=f"at_goal tolerance in meters (default: {DEFAULT_AT_GOAL_TOL_M})",
    )
    args = parser.parse_args()

    pose, _planning = poll_pose_and_planning()
    if pose is None:
        print("Failed to read /reeman/pose.", file=sys.stderr)
        return 1

    nav_status = get_move_status(args.move_id)
    if nav_status is None:
        print("Failed to read /reeman/nav_status.", file=sys.stderr)
        return 1

    out: dict[str, Any] = {
        "/reeman/pose": pose,
        "/reeman/nav_status": nav_status,
    }

    if args.target_x is not None and args.target_y is not None:
        out["distance_m"] = round(
            distance_to_target(pose, args.target_x, args.target_y) or 0.0,
            3,
        )
        out["at_goal"] = at_goal(
            pose,
            args.target_x,
            args.target_y,
            tol_m=args.tol_m,
        )

    print_json(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
