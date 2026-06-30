#!/usr/bin/env python3
"""Read robot pose from WebSocket ``/tracked_pose`` (same data as ``get_robot_position``)."""

from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics

TOPIC = "/tracked_pose"


def get_pose(timeout: float | None = None) -> dict | None:
    """Subscribe to WebSocket ``/tracked_pose`` (world-frame meters, radians CCW from East)."""
    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, [TOPIC], timeout=timeout)
        return got.get(TOPIC)
    except Exception as e:
        print(f"WebSocket error: {e}")
        return None


if __name__ == "__main__":
    run_single_topic_cli(
        TOPIC,
        description="WebSocket /tracked_pose (alias of get_robot_position; pos [x,y], ori)",
    )
