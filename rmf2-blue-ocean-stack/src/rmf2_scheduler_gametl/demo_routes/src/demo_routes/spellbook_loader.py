# Copyright 2024-2026 ROS Industrial Consortium Asia Pacific
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Bootstrap autoxing_bridge/spellbook for scheduler demo routes."""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path
from types import ModuleType

_SPELLBOOK_MODULES = (
    "credentials._config",
    "credentials",
    "api_client",
    "navigate",
    "pick_rack",
)
_cached_endpoint: str | None = None


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "config" / "config.env").is_file():
            return parent
    # Container fallback when only /vda_demo is mounted.
    vda = os.environ.get("VDA_DEMO_ROOT", "").strip()
    if vda:
        return Path(vda)
    raise RuntimeError(
        "Cannot locate repo root (config/config.env) — set VDA_DEMO_ROOT or "
        "AUTOXING_SPELLBOOK_DIR."
    )


def spellbook_dir() -> Path:
    env = os.environ.get("AUTOXING_SPELLBOOK_DIR", "").strip()
    if env:
        root = Path(env).expanduser()
        if not root.is_absolute():
            root = _repo_root() / root
        return root.resolve()
    return (
        _repo_root()
        / "src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean"
        / "autoxing"
        / "autoxing_bridge"
        / "spellbook"
    ).resolve()


def _ensure_constants_yml(cmd_dir: Path) -> None:
    yml = cmd_dir / "credentials" / "CONSTANTS.yml"
    example = cmd_dir / "credentials" / "CONSTANTS.example.yml"
    if not yml.is_file() and example.is_file():
        shutil.copy(example, yml)
    if not yml.is_file():
        raise RuntimeError(
            f"Spellbook robot config not found: {yml} "
            f"(copy CONSTANTS.example.yml to CONSTANTS.yml)."
        )


def load_pick_rack(endpoint: str) -> ModuleType:
    """Point spellbook credentials at ``endpoint`` and return ``pick_rack`` module."""
    global _cached_endpoint

    cmd_dir = spellbook_dir()
    if not cmd_dir.is_dir():
        raise RuntimeError(f"Spellbook directory not found: {cmd_dir}")

    demo_root = cmd_dir.parent.parent
    for path in (str(demo_root), str(cmd_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)

    os.environ["AUTOXING_BASE_URL"] = endpoint.rstrip("/")
    _ensure_constants_yml(cmd_dir)

    endpoint_changed = _cached_endpoint != endpoint
    _cached_endpoint = endpoint

    if endpoint_changed or "pick_rack" not in sys.modules:
        for name in _SPELLBOOK_MODULES:
            if name in sys.modules:
                importlib.reload(sys.modules[name])
            else:
                importlib.import_module(name)
    else:
        cred_cfg = importlib.import_module("credentials._config")
        cred_cfg.CONSTANTS = cred_cfg.robot_config()
        cred = importlib.import_module("credentials")
        cred.CONSTANTS = cred_cfg.CONSTANTS
        importlib.reload(sys.modules["api_client"])

    return sys.modules["pick_rack"]
