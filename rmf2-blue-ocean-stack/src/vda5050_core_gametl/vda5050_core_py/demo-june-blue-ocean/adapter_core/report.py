"""Render the one consolidated 'resolved config' block adapters log at startup."""

from __future__ import annotations

import os
import sys

from adapter_core.config import MASTER_URL


def print_resolved_config(
    config: dict, me: dict, *, endpoint_env: str, extra_lines: list[str] | None = None
) -> None:
    """Emit the adapter's runtime config, making explicit that every field except
    ROBOT_ID + MASTER_URL + broker is resolved from the vda5050 master (keyed by
    robot_id), not from local files. ``extra_lines`` are appended verbatim (e.g.
    a robot's transform description)."""
    endpoint = me.get("endpoint") or os.environ.get(endpoint_env) or "?"
    lines = [
        "================ adapter resolved config ================",
        f"  robot_id      : {config['robot_id']}   (ROBOT_ID/hostname — local)",
        f"  master        : {MASTER_URL}   (MASTER_URL — local)",
        f"  broker        : {config['broker']}   (MQTT_BROKER — local)",
        f"  manufacturer  : {config['manufacturer']}   <- master /robots",
        f"  serial_number : {config['serial_number']}   <- master /robots",
        f"  client_id     : {config['client_id']}",
        f"  mqtt topic    : {config['interface']}/v2/"
        f"{config['manufacturer']}/{config['serial_number']}",
        f"  endpoint (IP) : {endpoint}   <- master /robots",
        f"  map_id        : {config['map_id']}   <- master /map",
        f"  home node     : {me.get('home') or '?'}   <- master /robots",
        *(extra_lines or []),
        "=========================================================",
    ]
    print("\n".join(lines), file=sys.stderr)
