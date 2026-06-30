#!/usr/bin/env python3
"""Jack device state — not exposed on Reeman FlyBoat REST API."""

import sys


def jack_state(timeout: float | None = None) -> dict | None:
    """Jack state is not available on Reeman FlyBoat (REST-only robot)."""
    del timeout
    print("Reeman FlyBoat has no jack-state REST endpoint.", file=sys.stderr)
    return None


if __name__ == "__main__":
    sys.exit(0 if jack_state() is not None else 1)
