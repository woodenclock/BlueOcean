"""Shared HTTP client for AXBot REST (port 8090)."""

from __future__ import annotations

import json
import sys
from typing import Any

import requests
from rich.console import Console
from rich.json import JSON

from credentials import CONSTANTS as ROBOT
from credentials import timeout_seconds

_console = Console()


def print_json(data: Any) -> None:
    """Pretty-print JSON API data to stdout with syntax highlighting."""
    _console.print(JSON.from_data(data, indent=2))


def base_url() -> str:
    return f"{ROBOT.PREFIX}{ROBOT.ROBOT_IP}".rstrip("/")


def request_api(
    method: str,
    path: str,
    *,
    json_body: Any | None = None,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
    prefer_text: bool = False,
    print_errors: bool = True,
) -> Any | None:
    """
    Perform ``method path`` against the configured robot.

    - JSON responses (200/201): parsed object (dict/list) or raw on failure to decode
    - 204 No Content: ``None``
    - ``prefer_text``: return response body as ``str`` (e.g. Chrony GET, job logs)
    """
    url = f"{base_url()}{path}"
    t = timeout if timeout is not None else timeout_seconds()
    try:
        r = requests.request(
            method.upper(),
            url,
            json=json_body,
            params=params,
            timeout=t,
        )
        r.raise_for_status()
        m = method.upper()
        if r.status_code == 204:
            if prefer_text:
                return ""
            if m in ("POST", "PUT", "PATCH", "DELETE"):
                return {}
            return None
        if not r.content:
            if prefer_text:
                return ""
            if m in ("POST", "PUT", "PATCH", "DELETE"):
                return {}
            return None
        ct = (r.headers.get("Content-Type") or "").lower()
        if prefer_text or "text/plain" in ct:
            return r.text
        try:
            return r.json()
        except ValueError:
            return r.text
    except requests.exceptions.ConnectionError as e:
        if print_errors:
            print(f"Connection error: {e}", file=sys.stderr)
    except requests.exceptions.Timeout as e:
        if print_errors:
            print(f"Timeout: {e}", file=sys.stderr)
    except requests.exceptions.HTTPError as e:
        if print_errors:
            print(f"HTTP error: {e}", file=sys.stderr)
            if e.response is not None and e.response.text:
                print(e.response.text[:800], file=sys.stderr)
    except requests.exceptions.RequestException as e:
        if print_errors:
            print(f"Request error: {e}", file=sys.stderr)
    return None


def parse_json_file(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
