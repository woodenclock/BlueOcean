#!/usr/bin/env python3
"""Alias for ``get_pose`` — WebSocket ``/tracked_pose``."""

from get_pose import TOPIC, get_pose

from ws_cli import run_single_topic_cli


def get_robot_position(timeout: float | None = None) -> dict | None:
    return get_pose(timeout=timeout)


if __name__ == "__main__":
    run_single_topic_cli(
        TOPIC,
        description="WebSocket /tracked_pose (pos [x,y], ori radians CCW from East)",
    )
