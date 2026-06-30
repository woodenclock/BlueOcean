#!/usr/bin/env python3
"""Jack device state — WebSocket ``/jack_state`` (state, progress, self-check fields)."""

from credentials import CONSTANTS as ROBOT

from ws_helper import ws_get_topics

TOPIC = "/jack_state"


def jack_state(timeout: float | None = None) -> dict | None:
    """Subscribe to WebSocket ``/jack_state`` (unknown | hold | jacking_up | jacking_down)."""
    try:
        got = ws_get_topics(ROBOT.ROBOT_IP, [TOPIC], timeout=timeout)
        return got.get(TOPIC)
    except Exception as e:
        print(f"WebSocket error: {e}")
        return None


if __name__ == "__main__":
    from ws_cli import run_single_topic_cli

    run_single_topic_cli(
        TOPIC,
        description="WebSocket /jack_state (state, progress 0–1, self_checking)",
    )
