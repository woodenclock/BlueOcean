"""Thin client for the VDA5050 master's read endpoints (/robots, /map, ...)."""

from __future__ import annotations

import json
import urllib.request

from adapter_core.config import MASTER_URL


def master_get(path: str) -> dict:
    """GET ``{MASTER_URL}{path}`` and return the decoded JSON body."""
    url = f"{MASTER_URL}{path}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())
