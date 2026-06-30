#!/usr/bin/env python3

from __future__ import annotations

import signal
import sys
from contextlib import contextmanager
from api_client import request_api

CANCEL_TIMEOUT_SEC = 4.0
CANCEL_RETRIES = 3


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


def cancel_move(*, timeout: float | None = None, print_errors: bool = True) -> dict | None:
    """PATCH /chassis/moves/current — cancel active navigation."""
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
