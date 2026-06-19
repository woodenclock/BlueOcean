"""Reeman→AutoXing 2D map transform: estimation, persistence, init policy.

AutoXing's map frame is the **master** frame; every coordinate published or
consumed over VDA5050 is master-frame. The Reeman adapter calls
``init_map_transform()`` once during init:

1. Fetch Reeman's current map + named waypoints (via the Reeman spellbook
   already on sys.path in the adapter process).
2. Fetch AutoXing's current map + overlay navigation points (direct REST,
   ``autoxing_client``). When online: match waypoints by name, estimate a
   similarity transform with ``nudged``, persist it to the cache, return it.
3. When AutoXing is offline: fall back to the cached transform from the last
   successful calibration **iff** the cached Reeman map name still matches
   the robot's current map. Otherwise return None — the adapter must then
   block navigation (a wrong-frame move is worse than no move). Env
   ``MAP_TF_ALLOW_IDENTITY=1`` downgrades that to an identity transform for
   demo/dry-run setups where both frames are known to coincide.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import nudged

from map_transform import autoxing_client

DEFAULT_CACHE_PATH = Path(
    os.environ.get(
        "MAP_TF_CACHE_PATH",
        Path.home() / ".cache" / "gametl" / "reeman_to_autoxing_tf.json",
    )
)
# Declarative transform file (master frame + per-adapter robot->master). Read
# when MAP_TF_MODE=file; written by image_calibrate. Lives in the repo's maps/
# dir alongside the onboard maps it is derived from, but MAP_TF_FILE overrides
# (compose sets it to the mounted /app/maps/map_transforms.yaml).
DEFAULT_TRANSFORM_FILE = Path(
    os.environ.get(
        # This module lives at maps/map_transform/, so parents[1] is the repo's
        # maps/ dir where map_transforms.yaml lives alongside the onboard maps.
        "MAP_TF_FILE",
        Path(__file__).resolve().parents[1] / "map_transforms.yaml",
    )
)
MIN_ANCHORS = int(os.environ.get("MAP_TF_MIN_ANCHORS", "3"))
MAX_MSE = float(os.environ.get("MAP_TF_MAX_MSE", "0.25"))  # m^2, nudged estimate_error
# Both frames are metric — a scale far from 1.0 means a bad anchor pair.
SCALE_WARN_TOL = 0.05

CACHE_VERSION = 1


def _log(msg: str) -> None:
    print(f"[map-tf] {msg}", file=sys.stderr)


def _allow_identity() -> bool:
    return os.environ.get("MAP_TF_ALLOW_IDENTITY", "").lower() in ("1", "true", "yes")


class CalibrationError(RuntimeError):
    """Anchor matching or transform estimation failed validation."""


@dataclass
class MapTransform:
    """Similarity transform robot(Reeman)→master(AutoXing).

    Forward map: ``x' = s*x - r*y + tx``, ``y' = r*x + s*y + ty``
    (nudged convention: ``s = scale*cos(rot)``, ``r = scale*sin(rot)``).
    """

    s: float
    r: float
    tx: float
    ty: float
    anchors: list[str] = field(default_factory=list)
    mse: float | None = None
    reeman_map: dict[str, Any] = field(default_factory=dict)
    autoxing_map: dict[str, Any] = field(default_factory=dict)
    calibrated_at: float | None = None
    source: str = "fresh"  # fresh | cache | identity | static

    # -- frame conversion -------------------------------------------------

    @property
    def scale(self) -> float:
        return math.hypot(self.s, self.r)

    @property
    def rotation(self) -> float:
        return math.atan2(self.r, self.s)

    def to_master(
        self, x: float, y: float, theta: float | None = None
    ) -> tuple[float, float, float | None]:
        mx = self.s * x - self.r * y + self.tx
        my = self.r * x + self.s * y + self.ty
        mtheta = None if theta is None else _wrap_angle(theta + self.rotation)
        return mx, my, mtheta

    def to_robot(
        self, x: float, y: float, theta: float | None = None
    ) -> tuple[float, float, float | None]:
        det = self.s * self.s + self.r * self.r
        dx, dy = x - self.tx, y - self.ty
        rx = (self.s * dx + self.r * dy) / det
        ry = (-self.r * dx + self.s * dy) / det
        rtheta = None if theta is None else _wrap_angle(theta - self.rotation)
        return rx, ry, rtheta

    # -- construction / persistence ---------------------------------------

    @classmethod
    def identity(cls) -> "MapTransform":
        return cls(s=1.0, r=0.0, tx=0.0, ty=0.0, source="identity")

    @classmethod
    def from_similarity(
        cls,
        tx: float,
        ty: float,
        theta: float,
        scale: float = 1.0,
        *,
        source: str = "file",
    ) -> "MapTransform":
        """Build from human-readable similarity params (theta in radians)."""
        return cls(
            s=scale * math.cos(theta),
            r=scale * math.sin(theta),
            tx=tx,
            ty=ty,
            source=source,
        )

    @classmethod
    def static_from_env(cls) -> "MapTransform":
        """Fixed Reeman→AutoXing transform from MAP_TF_STATIC_TX/TY/THETA
        (meters / radians, all default 0 → identity). For setups where both
        on-robot maps share one frame (both aliased to the master map) or the
        offset has been measured by hand."""
        tx = float(os.environ.get("MAP_TF_STATIC_TX", "0"))
        ty = float(os.environ.get("MAP_TF_STATIC_TY", "0"))
        theta = float(os.environ.get("MAP_TF_STATIC_THETA", "0"))
        return cls(
            s=math.cos(theta), r=math.sin(theta), tx=tx, ty=ty, source="static"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CACHE_VERSION,
            "s": self.s,
            "r": self.r,
            "tx": self.tx,
            "ty": self.ty,
            "anchors": self.anchors,
            "mse": self.mse,
            "reeman_map": self.reeman_map,
            "autoxing_map": self.autoxing_map,
            "calibrated_at": self.calibrated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MapTransform":
        return cls(
            s=float(data["s"]),
            r=float(data["r"]),
            tx=float(data["tx"]),
            ty=float(data["ty"]),
            anchors=list(data.get("anchors", [])),
            mse=data.get("mse"),
            reeman_map=dict(data.get("reeman_map", {})),
            autoxing_map=dict(data.get("autoxing_map", {})),
            calibrated_at=data.get("calibrated_at"),
            source="cache",
        )

    def describe(self) -> str:
        return (
            f"source={self.source} scale={self.scale:.4f} "
            f"rotation={math.degrees(self.rotation):.2f}deg "
            f"translation=({self.tx:.3f}, {self.ty:.3f}) "
            f"mse={self.mse if self.mse is None else f'{self.mse:.4f}'} "
            f"anchors={self.anchors} "
            f"reeman_map={self.reeman_map.get('name')!r} "
            f"autoxing_map={self.autoxing_map.get('map_name')!r} "
            f"(uid={self.autoxing_map.get('uid')!r}, "
            f"version={self.autoxing_map.get('map_version')!r})"
        )


def _wrap_angle(theta: float) -> float:
    return math.atan2(math.sin(theta), math.cos(theta))


def _norm_name(name: Any) -> str:
    return str(name).strip().casefold()


def match_anchors(
    reeman_wps: list[dict], autoxing_pts: list[dict]
) -> tuple[list[list[float]], list[list[float]], list[str]]:
    """Pair up waypoints by normalized name. Returns (reeman_xy, autoxing_xy, names)."""
    ax_by_name: dict[str, dict] = {}
    for p in autoxing_pts or []:
        if p.get("name") is not None and p.get("x") is not None:
            ax_by_name.setdefault(_norm_name(p["name"]), p)

    reeman_xy: list[list[float]] = []
    autoxing_xy: list[list[float]] = []
    names: list[str] = []
    for wp in reeman_wps or []:
        if wp.get("name") is None or wp.get("x") is None or wp.get("y") is None:
            continue
        key = _norm_name(wp["name"])
        ax = ax_by_name.get(key)
        if ax is None:
            continue
        reeman_xy.append([float(wp["x"]), float(wp["y"])])
        autoxing_xy.append([float(ax["x"]), float(ax["y"])])
        names.append(str(wp["name"]))
    return reeman_xy, autoxing_xy, names


def compute_transform(
    reeman_wps: list[dict],
    autoxing_pts: list[dict],
    *,
    min_anchors: int = MIN_ANCHORS,
    max_mse: float = MAX_MSE,
) -> MapTransform:
    """Estimate Reeman→AutoXing transform from shared waypoint names via nudged."""
    reeman_xy, autoxing_xy, names = match_anchors(reeman_wps, autoxing_pts)
    if len(names) < min_anchors:
        raise CalibrationError(
            f"Only {len(names)} shared waypoint name(s) between the two maps "
            f"(need >= {min_anchors}). Reeman waypoints: "
            f"{sorted(_norm_name(w.get('name')) for w in reeman_wps or [])}; "
            f"AutoXing points: "
            f"{sorted(_norm_name(p.get('name')) for p in autoxing_pts or [])}"
        )
    if len(names) < 4:
        _log(f"Only {len(names)} anchors matched — 4+ recommended for a robust fit.")

    est = nudged.estimate(reeman_xy, autoxing_xy)
    mse = nudged.estimate_error(est, reeman_xy, autoxing_xy)
    (tx, ty) = est.get_translation()
    scale = est.get_scale()
    rotation = est.get_rotation()
    tf = MapTransform(
        s=scale * math.cos(rotation),
        r=scale * math.sin(rotation),
        tx=tx,
        ty=ty,
        anchors=names,
        mse=mse,
        calibrated_at=time.time(),
    )

    if mse > max_mse:
        raise CalibrationError(
            f"Calibration MSE {mse:.4f} exceeds MAP_TF_MAX_MSE={max_mse} "
            f"({tf.describe()}) — check anchor placement/naming."
        )
    if abs(tf.scale - 1.0) > SCALE_WARN_TOL:
        _log(
            f"WARNING: estimated scale {tf.scale:.4f} deviates from 1.0 — both "
            f"frames should be metric; a waypoint pair is likely mismatched."
        )
    return tf


# -- cache ----------------------------------------------------------------


def save_cache(tf: MapTransform, path: Path = DEFAULT_CACHE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tf.to_dict(), indent=2))
    _log(f"Calibration cached at {path}")


def load_cache(path: Path = DEFAULT_CACHE_PATH) -> MapTransform | None:
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return MapTransform.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        _log(f"Ignoring unreadable calibration cache {path}: {exc}")
        return None


# -- declarative transform file -------------------------------------------


def load_transform_file(
    path: Path | str, adapter: str
) -> tuple[str | None, MapTransform]:
    """Load one adapter's robot->master transform from a transform YAML.

    Returns ``(master_frame, transform)``. Raises ``CalibrationError`` if the
    adapter is missing. The adapter named by ``master_frame``'s owner is the
    identity transform (its robot frame is the master frame).
    """
    import yaml  # noqa: PLC0415 — optional dep, only needed for file mode

    data = yaml.safe_load(Path(path).read_text()) or {}
    master = data.get("master_frame")
    adapters = data.get("adapters") or {}
    entry = adapters.get(adapter)
    if entry is None:
        raise CalibrationError(
            f"adapter {adapter!r} not found in transform file {path} "
            f"(have: {sorted(adapters)})"
        )
    rt = entry.get("robot_to_master") or {}
    tf = MapTransform.from_similarity(
        tx=float(rt.get("tx", 0.0)),
        ty=float(rt.get("ty", 0.0)),
        theta=float(rt.get("theta", 0.0)),
        scale=float(rt.get("scale", 1.0)),
        source="file",
    )
    tf.anchors = [f"file:{adapter}"]
    tf.reeman_map = {"name": entry.get("map_name")}
    tf.autoxing_map = {"map_name": master}
    return master, tf


# -- reeman side (spellbook on sys.path inside the adapter process) --------


def _ensure_reeman_spellbook() -> Path:
    """Bootstrap Reeman spellbook without importing ``reeman_bridge`` package.

    ``reeman_bridge/__init__.py`` eagerly imports ``bridge.py``, which pulls
    in ``vda5050_core_py`` — not needed for map calibration.
    """
    import importlib.util

    spellbook_path = (
        Path(__file__).resolve().parent.parent / "reeman_bridge" / "_spellbook_path.py"
    )
    spec = importlib.util.spec_from_file_location(
        "reeman_bridge._spellbook_path",
        spellbook_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Reeman spellbook bootstrap: {spellbook_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ensure_spellbook()


def _fetch_reeman_side(artifact_dir: Path) -> tuple[dict | None, list[dict] | None]:
    """Current map metadata + named waypoints from the Reeman robot.

    Also exports the robot's map next to the cache for provenance/visual
    checks (best-effort).
    """
    _ensure_reeman_spellbook()
    from get_current_map import get_current_map  # noqa: PLC0415 — spellbook
    from get_waypoints import get_waypoints  # noqa: PLC0415

    current = get_current_map()
    waypoints = get_waypoints()

    try:
        from download_map import download_reeman_map  # noqa: PLC0415

        name = (current or {}).get("name") or "current"
        saved = download_reeman_map(str(artifact_dir / f"reeman_{name}"), map_name=name)
        if saved:
            _log(f"Reeman map export saved: {saved}")
    except Exception as exc:  # noqa: BLE001 — provenance only, never fatal
        _log(f"Reeman map export skipped: {exc}")

    return current, waypoints


def _fetch_autoxing_side(artifact_dir: Path) -> tuple[dict | None, list[dict] | None]:
    """Current map metadata + overlay navigation points from the AutoXing robot."""
    current = autoxing_client.get_current_map()
    if current is None:
        return None, None
    map_id = current.get("id")
    if map_id is None:
        _log(f"AutoXing current map has no id: {current}")
        return current, None
    detail = autoxing_client.fetch_map_detail(int(map_id))
    if detail is None:
        return current, None
    points = autoxing_client.extract_navigation_points(detail)

    name = current.get("map_name") or f"map_{map_id}"
    saved = autoxing_client.download_map_image(detail, artifact_dir / f"autoxing_{name}.png")
    if saved:
        _log(f"AutoXing map image saved: {saved}")

    return current, points


# -- init-phase orchestrator ------------------------------------------------


def init_map_transform(cache_path: Path | None = None) -> MapTransform | None:
    """Calibrate at adapter init; implements the AutoXing-offline fallback rule.

    Returns None when no trustworthy transform exists — the caller must block
    navigation in that case.

    ``MAP_TF_MODE=file`` reads the declarative transform file (``MAP_TF_FILE``,
    default ``map_transforms.yaml``) for the adapter named by ``MAP_TF_ADAPTER``
    (default ``reeman``). ``MAP_TF_MODE=static`` bypasses calibration entirely
    and returns the transform from ``MAP_TF_STATIC_TX/TY/THETA`` (default
    identity).
    """
    mode = os.environ.get("MAP_TF_MODE", "").lower()
    if mode == "file":
        tf_path = os.environ.get("MAP_TF_FILE", DEFAULT_TRANSFORM_FILE)
        adapter = os.environ.get("MAP_TF_ADAPTER", "reeman")
        try:
            master, tf = load_transform_file(tf_path, adapter)
        except (OSError, CalibrationError, ValueError, TypeError) as exc:
            _log(f"Transform file load failed ({tf_path}): {exc}")
            if _allow_identity():
                _log("MAP_TF_ALLOW_IDENTITY=1 — using identity transform.")
                return MapTransform.identity()
            return None
        _log(
            f"MAP_TF_MODE=file — master={master!r} adapter={adapter!r}: "
            f"{tf.describe()}"
        )
        return tf
    if mode == "static":
        tf = MapTransform.static_from_env()
        _log(f"MAP_TF_MODE=static — skipping calibration: {tf.describe()}")
        return tf

    cache_path = Path(cache_path or DEFAULT_CACHE_PATH)
    artifact_dir = cache_path.parent / "maps"

    try:
        reeman_map, reeman_wps = _fetch_reeman_side(artifact_dir)
    except Exception as exc:  # noqa: BLE001 — robot/spellbook unavailable
        _log(f"Reeman map/waypoint fetch failed: {exc}")
        reeman_map, reeman_wps = None, None

    autoxing_map, autoxing_pts = _fetch_autoxing_side(artifact_dir)

    if autoxing_pts and reeman_wps:
        try:
            tf = compute_transform(reeman_wps, autoxing_pts)
        except CalibrationError as exc:
            _log(f"Calibration failed: {exc}")
        else:
            tf.reeman_map = reeman_map or {}
            tf.autoxing_map = autoxing_map or {}
            save_cache(tf, cache_path)
            _log(f"Fresh calibration OK: {tf.describe()}")
            return tf
    else:
        _log(
            "AutoXing master map unavailable"
            if not autoxing_pts
            else "Reeman waypoints unavailable"
        )

    # Fallback: last successful calibration, validated against Reeman's map.
    cached = load_cache(cache_path)
    if cached is not None:
        current_name = (reeman_map or {}).get("name")
        cached_name = cached.reeman_map.get("name")
        if current_name is not None and cached_name == current_name:
            _log(
                f"Using cached calibration (AutoXing offline — staleness of the "
                f"master map cannot be verified): {cached.describe()}"
            )
            return cached
        _log(
            f"Cached calibration rejected: Reeman map changed "
            f"(cached={cached_name!r}, current={current_name!r})."
        )

    if _allow_identity():
        _log("WARNING: MAP_TF_ALLOW_IDENTITY=1 — using identity transform.")
        return MapTransform.identity()

    _log(
        "No valid Reeman→AutoXing transform (AutoXing offline and no usable "
        "cache). Navigation must stay blocked until calibration succeeds."
    )
    return None
