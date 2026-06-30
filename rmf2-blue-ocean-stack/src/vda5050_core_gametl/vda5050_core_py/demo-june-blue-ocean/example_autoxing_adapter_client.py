#!/usr/bin/env python3
"""Entry point for the Autoxing VDA5050 adapter client.

The implementation lives in the ``autoxing`` package (and the shared
``adapter_core``); this file stays only as the stable, compose-referenced
entry point::

    python3 example_autoxing_adapter_client.py [--disable-state-log]

    # publish demo order from the umbrella repo root (requires mosquitto)
    uv run fixtures/run_publish_mqtt_route.py --wait-route
"""

import sys

from autoxing.adapter import main

if __name__ == "__main__":
    sys.exit(main())
