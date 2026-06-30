"""Load multi-robot config from ``CONSTANTS.yml`` (active entry selected by index)."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import yaml

CREDENTIALS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = CREDENTIALS_DIR / "CONSTANTS.yml"
LEGACY_PY_PATH = CREDENTIALS_DIR / "CONSTANTS.py"
EXAMPLE_PATH = CREDENTIALS_DIR / "CONSTANTS.example.yml"

DEFAULT_TIMEOUT_MS = 30_000


class RobotConfig(SimpleNamespace):
    PREFIX: str
    ROBOT_NAME: str
    ROBOT_IP: str
    TIMEOUT_MS: int


def timeout_seconds(cfg: RobotConfig | None = None) -> float:
    """Active robot timeout in seconds (for ``requests`` / WebSocket)."""
    if cfg is None:
        cfg = robot_config()
    return cfg.TIMEOUT_MS / 1000.0


def _resolve_timeout_ms(data: dict[str, Any], entry: dict[str, Any]) -> int:
    raw = entry.get("timeout_ms", data.get("timeout_ms", DEFAULT_TIMEOUT_MS))
    try:
        ms = int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError("CONSTANTS.yml: timeout_ms must be an integer (milliseconds)") from e
    if ms < 1:
        raise ValueError("CONSTANTS.yml: timeout_ms must be >= 1")
    return ms


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping at top level")
    return data


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def _read_legacy_py() -> dict[str, Any]:
    if not LEGACY_PY_PATH.is_file():
        raise FileNotFoundError(f"Legacy config not found: {LEGACY_PY_PATH}")
    spec = importlib.util.spec_from_file_location("_legacy_constants", LEGACY_PY_PATH)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load {LEGACY_PY_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {
        "active_index": 0,
        "prefix": str(getattr(mod, "PREFIX", "http://")),
        "timeout_ms": DEFAULT_TIMEOUT_MS,
        "robots": [
            {
                "name": str(getattr(mod, "ROBOT_NAME", "robot")),
                "robot_ip": str(getattr(mod, "ROBOT_IP", "")),
            },
        ],
    }


def migrate_from_constants_py(*, overwrite: bool = False) -> Path:
    """Create ``CONSTANTS.yml`` from gitignored ``CONSTANTS.py`` if present."""
    if CONFIG_PATH.is_file() and not overwrite:
        return CONFIG_PATH
    data = _read_legacy_py()
    _save_yaml(CONFIG_PATH, data)
    return CONFIG_PATH


def ensure_config() -> dict[str, Any]:
    if CONFIG_PATH.is_file():
        return _load_yaml(CONFIG_PATH)
    if LEGACY_PY_PATH.is_file():
        migrate_from_constants_py()
        return _load_yaml(CONFIG_PATH)
    if EXAMPLE_PATH.is_file():
        raise FileNotFoundError(
            f"Copy {EXAMPLE_PATH.name} to {CONFIG_PATH.name} and set active_index / robots."
        )
    raise FileNotFoundError(
        f"Missing {CONFIG_PATH.name} — copy from {EXAMPLE_PATH.name} or migrate CONSTANTS.py."
    )


def list_robots(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if data is None:
        data = ensure_config()
    robots = data.get("robots")
    if not isinstance(robots, list) or not robots:
        raise ValueError("CONSTANTS.yml: robots must be a non-empty list")
    out: list[dict[str, Any]] = []
    for i, entry in enumerate(robots):
        if not isinstance(entry, dict):
            raise ValueError(f"CONSTANTS.yml: robots[{i}] must be a mapping")
        name = str(entry.get("name") or entry.get("robot_name") or f"robot_{i}")
        ip = str(entry.get("robot_ip") or entry.get("ROBOT_IP") or "")
        if not ip:
            raise ValueError(f"CONSTANTS.yml: robots[{i}] missing robot_ip")
        out.append(
            {
                "name": name,
                "robot_ip": ip,
                "timeout_ms": _resolve_timeout_ms(data, entry),
            }
        )
    return out


def active_index(data: dict[str, Any] | None = None) -> int:
    if data is None:
        data = ensure_config()
    try:
        idx = int(data.get("active_index", 0))
    except (TypeError, ValueError) as e:
        raise ValueError("CONSTANTS.yml: active_index must be an integer") from e
    robots = list_robots(data)
    if idx < 0 or idx >= len(robots):
        raise ValueError(f"CONSTANTS.yml: active_index {idx} out of range (0..{len(robots) - 1})")
    return idx


def set_active_index(index: int) -> RobotConfig:
    data = ensure_config()
    robots = list_robots(data)
    if index < 0 or index >= len(robots):
        raise ValueError(f"robot index {index} out of range (0..{len(robots) - 1})")
    data["active_index"] = index
    _save_yaml(CONFIG_PATH, data)
    return robot_config(data)


def _robot_ip_from_env() -> str | None:
    """``AUTOXING_ROBOT_IP`` (host:port) or ``AUTOXING_BASE_URL`` (http://host:port)."""
    raw = os.environ.get("AUTOXING_ROBOT_IP", "").strip()
    if raw:
        return raw
    base = os.environ.get("AUTOXING_BASE_URL", "").strip()
    if not base:
        return None
    parsed = urlparse(base if "://" in base else f"http://{base}")
    if not parsed.hostname:
        return None
    if parsed.port:
        return f"{parsed.hostname}:{parsed.port}"
    return parsed.hostname


def robot_config(data: dict[str, Any] | None = None) -> RobotConfig:
    if data is None:
        data = ensure_config()
    robots = list_robots(data)
    idx = active_index(data)
    entry = robots[idx]
    prefix = str(data.get("prefix", "http://"))
    robot_ip = _robot_ip_from_env() or str(entry["robot_ip"])
    return RobotConfig(
        PREFIX=prefix,
        ROBOT_NAME=str(entry["name"]),
        ROBOT_IP=robot_ip,
        TIMEOUT_MS=int(entry["timeout_ms"]),
    )


CONSTANTS = robot_config()
