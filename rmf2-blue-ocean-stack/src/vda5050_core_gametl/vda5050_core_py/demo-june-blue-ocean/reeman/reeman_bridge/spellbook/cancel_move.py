#!/usr/bin/env python3

from __future__ import annotations

import requests
import signal
import sys

from api_client import request_api
from contextlib import contextmanager
from credentials import CONSTANTS as ROBOT

CANCEL_TIMEOUT_SEC = 4.0
CANCEL_RETRIES = 3


def _robot_base_url() -> str:
    prefix = getattr(ROBOT, "PREFIX", "http://")
    ip = getattr(ROBOT, "ROBOT_IP")
    return f"{prefix}{ip}".rstrip("/")


@contextmanager
def _ignore_sigint():
    """Let cancel PATCH finish even if the user presses Ctrl+C again."""
    try:
        old = signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (ValueError, OSError):
        old = None
    try:
        yield
    finally:
        if old is not None:
            signal.signal(signal.SIGINT, old)


def cancel_reeman_move(timeout: float | None = None) -> dict | None:
    """Cancel Reeman active navigation via REST API."""
    try:
        resp = requests.post(
            f"{_robot_base_url()}/cmd/cancel_goal",
            json={},
            timeout=timeout or CANCEL_TIMEOUT_SEC,
        )
        resp.raise_for_status()

        try:
            data = resp.json()
        except ValueError:
            data = {}

        return data if isinstance(data, dict) else {"result": data}

    except Exception as e:
        print(f"Reeman REST error: {e}", file=sys.stderr)
        return None


def cancel_openapi_move(
    *, timeout: float | None = None, print_errors: bool = True
) -> dict | None:
    """PATCH /chassis/moves/current — fallback cancel active navigation."""
    data = request_api(
        "PATCH",
        "/chassis/moves/current",
        json_body={"state": "cancelled"},
        timeout=timeout if timeout is not None else CANCEL_TIMEOUT_SEC,
        print_errors=print_errors,
    )
    if isinstance(data, dict):
        return data
    return data if data is None else {"result": data}


def cancel_move(*, timeout: float | None = None, print_errors: bool = True) -> dict | None:
    """
    Cancel active navigation.

    Reeman FlyBoat uses REST API.
    Existing OpenAPI REST path is kept as fallback.
    """
    result = cancel_reeman_move(timeout=timeout)
    if result is not None:
        return result

    return cancel_openapi_move(timeout=timeout, print_errors=print_errors)


def cancel_move_robust(*, retries: int = CANCEL_RETRIES) -> bool:
    """
    Send cancel with SIGINT ignored and retries.

    Returns True when the robot accepts the PATCH (HTTP 2xx).
    """
    for attempt in range(1, retries + 1):
        with _ignore_sigint():
            try:
                result = cancel_move(
                    timeout=CANCEL_TIMEOUT_SEC,
                    print_errors=(attempt == retries),
                )
            except KeyboardInterrupt:
                result = None
        if result is not None:
            print("Move cancel acknowledged by robot.", file=sys.stderr)
            return True
        if attempt < retries:
            print(
                f"Cancel attempt {attempt}/{retries} failed — retrying…",
                file=sys.stderr,
            )
    print(
        "Cancel FAILED after retries. Run: cancel_move",
        file=sys.stderr,
    )
    return False


if __name__ == "__main__":
    ok = cancel_move_robust()
    raise SystemExit(0 if ok else 1)
