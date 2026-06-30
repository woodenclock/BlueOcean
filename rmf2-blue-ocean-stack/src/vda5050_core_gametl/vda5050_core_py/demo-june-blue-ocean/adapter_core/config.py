"""Adapter runtime config.

The ONLY local inputs to an adapter are ``ROBOT_ID`` (the unified robots.yaml id;
falls back to the container hostname, which compose sets to the robot_id) and
``MASTER_URL``. Everything else — manufacturer / serial_number / client_id (and
downstream the endpoint IP, map_id, home node, transform) — is resolved from the
vda5050 master keyed by robot_id (see :mod:`adapter_core.identity`). The
``VDA5050_*`` envs below stay as explicit overrides / offline fallbacks only.
"""

from __future__ import annotations

import os
import socket

# The VDA5050 master is the single map/robots authority.
MASTER_URL = os.environ.get("MASTER_URL", "http://vda5050:8000").rstrip("/")


def base_config(
    *, default_client_id: str, default_manufacturer: str, default_serial: str
) -> dict:
    """Common CONFIG shared by every adapter; robot packages extend the result."""
    return {
        "robot_id": os.environ.get("ROBOT_ID") or socket.gethostname(),
        "broker": os.environ.get("MQTT_BROKER", "tcp://localhost:1883"),
        "client_id": os.environ.get("VDA5050_CLIENT_ID", default_client_id),
        "interface": "uagv",
        "protocol_version": "2.1.0",
        "manufacturer": os.environ.get("VDA5050_MANUFACTURER", default_manufacturer),
        "serial_number": os.environ.get("VDA5050_SERIAL", default_serial),
        "poll_interval": 1.0,
        "nav_timeout": 300.0,
        "map_id": os.environ.get("VDA5050_MAP_ID", "From Mapping 40"),
    }
