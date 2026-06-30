#!/usr/bin/env python3

from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics


def get_battery_state(timeout: float | None = None) -> dict | None:
    """Subscribe once to WebSocket ``/battery_state``."""
    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, ["/battery_state"], timeout=timeout)
        return got.get("/battery_state")
    except Exception as e:
        print(f"WebSocket error: {e}")
        return None


if __name__ == "__main__":
    run_single_topic_cli("/battery_state", description="WebSocket /battery_state")
