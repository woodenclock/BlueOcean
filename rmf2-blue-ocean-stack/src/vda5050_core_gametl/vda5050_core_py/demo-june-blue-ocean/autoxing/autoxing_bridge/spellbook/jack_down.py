#!/usr/bin/env python3
"""Lower jack device — POST /services/jack_down, then wait until physically down.

Completion is read off the WebSocket ``/jack_state`` stream. A *down* motion runs
``state="jacking_down"`` with ``progress`` descending 1.0 → 0.0 and finishes by
returning to ``state="hold"`` (progress 0.0). So the done signal is the
``jacking_down → hold`` transition (equivalently progress reaching 0.0) — NOT
progress reaching 1.0 (that is what a jack_*up* does). Waiting for 1.0 here hangs
forever, which is the bug this guards against.
"""

import time

from api_client import print_json, request_api

from jack_state import jack_state

# Treat progress at/under this as fully lowered.
_DONE_PROGRESS = 0.02
# If the jack never starts moving (already down / idempotent call), stop waiting
# once we've seen this many consecutive idle "hold" reads so we don't hang.
_IDLE_HOLD_READS = 4


def _wait_until_down(*, timeout: float, poll_interval: float) -> bool:
    """Poll ``/jack_state`` until the jack settles down. True if confirmed down.

    Done when we've seen ``jacking_down`` and then ``hold`` (the documented
    transition), or progress has descended to ~0.0. A jack that is already down
    (never enters ``jacking_down``) is treated as done after a few idle ``hold``
    reads so the call is idempotent instead of blocking for the full timeout.
    """
    deadline = time.monotonic() + timeout
    seen_jacking_down = False
    idle_hold_reads = 0

    while time.monotonic() < deadline:
        snap = jack_state(timeout=poll_interval + 1.0)
        if not isinstance(snap, dict):
            time.sleep(poll_interval)
            continue

        state = snap.get("state")
        progress = snap.get("progress")

        if state == "jacking_down":
            seen_jacking_down = True
            idle_hold_reads = 0
            # Some firmware holds state="jacking_down" through the final 0.0
            # frame before flipping to "hold"; count that as down.
            if isinstance(progress, (int, float)) and progress <= _DONE_PROGRESS:
                return True
        elif state == "hold":
            if seen_jacking_down:
                # prev=jacking_down, now=hold → motion complete.
                return True
            # Never moved — likely already lowered. Confirm over a few reads.
            idle_hold_reads += 1
            if idle_hold_reads >= _IDLE_HOLD_READS:
                return True
        else:
            idle_hold_reads = 0

        time.sleep(poll_interval)

    return False


def jack_down(
    *, wait: bool = True, timeout: float = 30.0, poll_interval: float = 0.5
) -> dict | None:
    """POST /services/jack_down; block until the jack is down (``wait=True``).

    Returns the POST response dict. With ``wait=True`` the call does not return
    until ``/jack_state`` confirms the jack settled to ``hold`` (or the timeout
    elapses, which is logged); pass ``wait=False`` for fire-and-forget.
    """
    data = request_api("POST", "/services/jack_down", json_body={})
    if not isinstance(data, dict):
        return data
    if wait and not _wait_until_down(timeout=timeout, poll_interval=poll_interval):
        print(f"jack_down: timed out after {timeout:.0f}s waiting for jack to lower")
    return data


if __name__ == "__main__":
    out = jack_down()
    if out is not None:
        print_json(out)
