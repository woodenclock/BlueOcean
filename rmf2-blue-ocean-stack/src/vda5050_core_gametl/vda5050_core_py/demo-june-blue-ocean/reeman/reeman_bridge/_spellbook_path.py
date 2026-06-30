"""Bootstrap imports from vendored spellbook/."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_DEFAULT_SPELLBOOK_DIR = Path(__file__).resolve().parent / "spellbook"
_SPELLBOOK_CONFIGURED = False


def _repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "config.env").is_file():
            return parent
    return None


def commands_dir() -> Path:
    """Return resolved spellbook commands directory."""
    env = os.environ.get("REEMAN_SPELLBOOK_DIR", "").strip()
    if env:
        root = Path(env).expanduser()
        if not root.is_absolute():
            repo = _repo_root()
            root = (repo / root) if repo is not None else Path.cwd() / root
    else:
        root = _DEFAULT_SPELLBOOK_DIR
    return root.resolve()


def ensure_spellbook() -> Path:
    """Add spellbook/ to sys.path and verify robot config exists."""
    global _SPELLBOOK_CONFIGURED
    cmd_dir = commands_dir()
    credentials_yml = cmd_dir / "credentials" / "CONSTANTS.yml"
    credentials_example = cmd_dir / "credentials" / "CONSTANTS.example.yml"

    if not cmd_dir.is_dir():
        raise RuntimeError(
            f"Spellbook directory not found: {cmd_dir}\n"
            "Set REEMAN_SPELLBOOK_DIR to the spellbook/ path or vend spellbook "
            "under reeman/reeman_bridge/spellbook/."
        )

    cmd_path = str(cmd_dir)
    if cmd_path not in sys.path:
        sys.path.insert(0, cmd_path)

    if not credentials_yml.is_file():
        hint = (
            f"Copy {credentials_example.name} to CONSTANTS.yml and set robot_ip."
            if credentials_example.is_file()
            else "Create CONSTANTS.yml with active robot IP."
        )
        raise RuntimeError(
            f"Spellbook robot config not found: {credentials_yml}\n{hint}"
        )

    _SPELLBOOK_CONFIGURED = True
    return cmd_dir
