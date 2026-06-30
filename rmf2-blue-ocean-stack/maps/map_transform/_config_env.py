"""Load the repo-root ``.env`` into ``os.environ`` (unset keys only)."""

from __future__ import annotations

import os
from pathlib import Path


def _repo_root(start: Path | None = None) -> Path | None:
    here = (start or Path(__file__)).resolve()
    for parent in here.parents:
        if (parent / ".env").is_file():
            return parent
    return None


def load_config_env(*, start: Path | None = None) -> Path | None:
    """Parse the repo-root ``.env`` and set env vars that are not already set."""
    root = _repo_root(start)
    if root is None:
        return None
    path = root / ".env"
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip()
    return path
