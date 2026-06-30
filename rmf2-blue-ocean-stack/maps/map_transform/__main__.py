"""Standalone calibration CLI: ``python -m map_transform``.

Runs the same init-phase calibration as the Reeman adapter (Reeman spellbook
+ AUTOXING_BASE_URL REST) and prints the resulting transform. Exit code 1
when no valid transform could be produced.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from map_transform._config_env import load_config_env
from map_transform.transform import DEFAULT_CACHE_PATH, init_map_transform


def main() -> int:
    load_config_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help=f"Calibration cache file (default: {DEFAULT_CACHE_PATH})",
    )
    args = parser.parse_args()

    tf = init_map_transform(cache_path=args.cache_path)
    if tf is None:
        print("Calibration FAILED — no valid transform.", file=sys.stderr)
        return 1
    print(tf.describe())
    return 0


if __name__ == "__main__":
    sys.exit(main())
