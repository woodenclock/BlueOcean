#!/usr/bin/env python3
"""One-shot sample of WebSocket `/map` (occupancy image payload may be large)."""

from credentials import CONSTANTS as ROBOT

from ws_cli import run_single_topic_cli
from ws_helper import ws_get_topics


def get_map_ws(timeout: float | None = None) -> dict | None:
    got = ws_get_topics(ROBOT.ROBOT_IP, ["/map"], timeout=timeout)
    return got.get("/map")


if __name__ == "__main__":
    run_single_topic_cli(
        "/map",
        description="WebSocket /map (large data field trimmed in tty)",
        trim_large_data=True,
    )
