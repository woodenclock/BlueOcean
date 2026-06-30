#!/usr/bin/env python3
"""Entry point for the Reeman VDA5050 adapter client.

The implementation lives in the ``reeman`` package (and the shared
``adapter_core``); this file stays only as the stable, compose-referenced
entry point::

    python3 example_reeman_adapter_client.py [--disable-state-log]
"""

import sys

from reeman.adapter import main

if __name__ == "__main__":
    sys.exit(main())
