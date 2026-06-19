"""Image-based Reeman→AutoXing calibration: register the two occupancy-grid
PNGs directly (no shared waypoints needed).

Both maps ship as ROS map_server assets (PNG + yaml origin/resolution). The
walls themselves are the calibration features: we binarize both images to
wall masks, brute-force the rotation with FFT phase correlation (scale is
known — both maps are 0.05 m/px), then compose the pixel transform with each
map's pixel→world geometry to get the metric Reeman→AutoXing similarity
transform in the exact ``MapTransform`` convention.

Usage (from maps/): the master frame is one robot's map dir, and each other
robot map dir is registered onto it. robot_id == folder name minus ``_map``,
and one ``adapters.<robot_id>`` entry is written per robot:

    uv run python -m map_transform.image_calibrate \
        --master-map-dir autoxing-1_map \
        --robot-map-dir reeman-1_map \
        --robot-map-dir reeman-2-blue_map

Writes a per-robot calibration cache (offline fallback) + an overlay png to
eyeball the alignment, and merges into maps/map_transforms.yaml (other adapters
preserved). map_name per robot is read from maps/robots.yaml onboard_map.name.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

from map_transform.transform import (
    DEFAULT_CACHE_PATH,
    DEFAULT_TRANSFORM_FILE,
    MapTransform,
    save_cache,
)

HERE = Path(__file__).resolve().parent.parent
# This module lives at maps/map_transform/, so HERE IS the repo's maps/ dir —
# the onboard occupancy maps + map_transforms.yaml live alongside it.
MAPS_DIR = HERE


def _log(msg: str) -> None:
    print(f"[img-cal] {msg}", file=sys.stderr)


def write_transform_file(
    path: Path,
    *,
    master_frame: str,
    master_key: str,
    adapter_key: str,
    robot_map_name: str,
    tf: MapTransform,
    response: float,
) -> None:
    """Merge ONE adapter's robot->master transform into the declarative YAML.

    Loads the existing file if present and preserves master_frame plus every
    other ``adapters.*`` entry, so calibrating robot N never clobbers robots
    1..N-1. Only ``adapters[adapter_key]`` is created/replaced; the identity
    ``adapters[master_key]`` (the master-frame robot, e.g. autoxing-1) is (re)added
    when missing.
    """
    import yaml  # noqa: PLC0415

    path = Path(path)
    data: dict = {}
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text())
            if isinstance(loaded, dict):
                data = loaded
        except yaml.YAMLError:
            data = {}

    data["master_frame"] = master_frame
    adapters = data.get("adapters")
    if not isinstance(adapters, dict):
        adapters = {}
    # The master robot's onboard frame IS the master frame -> identity. Keep it.
    adapters.setdefault(
        master_key,
        {
            "map_name": master_frame,
            "robot_to_master": {"tx": 0.0, "ty": 0.0, "theta": 0.0, "scale": 1.0},
        },
    )
    adapters[adapter_key] = {
        "map_name": robot_map_name,
        "robot_to_master": {
            "tx": round(tf.tx, 4),
            "ty": round(tf.ty, 4),
            "theta": round(tf.rotation, 6),
            "scale": round(tf.scale, 4),
        },
        "source": "image-registration",
        "response": round(response, 4),
    }
    data["adapters"] = adapters
    header = (
        "# Map-frame transforms for the VDA5050 real demo (single source of truth).\n"
        "# master_frame is the shared frame; each adapter entry (keyed by robot_id)\n"
        "# is robot->master as a 2D similarity (theta radians, scale ~1.0). Regenerate:\n"
        "#     cd maps && python -m map_transform.image_calibrate \\\n"
        "#         --master-map-dir autoxing-1_map --robot-map-dir reeman-1_map [...]\n"
        "# Consumed at adapter init when MAP_TF_MODE=file.\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + yaml.safe_dump(data, sort_keys=False))
    _log(f"Transform file written: {path}  (merged adapter '{adapter_key}')")


# -- map loading ------------------------------------------------------------


class GeoMap:
    """A map_server PNG+yaml pair with its pixel↔world geometry."""

    def __init__(self, yaml_path: Path):
        meta = yaml.safe_load(Path(yaml_path).read_text())
        self.resolution = float(meta["resolution"])
        self.origin = [float(v) for v in meta["origin"]]
        img_path = Path(yaml_path).parent / meta["image"]
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise SystemExit(f"Cannot read map image {img_path}")
        self.img = img
        self.h, self.w = img.shape
        self.occupied_thresh = float(meta.get("occupied_thresh", 0.65))
        if int(meta.get("negate", 0)):
            self.img = 255 - self.img
        self.name = img_path.stem

    def wall_mask(self) -> np.ndarray:
        """Occupied (wall) pixels as float32 0/1, lightly dilated."""
        walls = (self.img < (1.0 - self.occupied_thresh) * 255).astype(np.uint8)
        walls = cv2.dilate(walls, np.ones((3, 3), np.uint8))
        return walls.astype(np.float32)

    # map_server: origin = world pose of the lower-left corner; image row 0
    # is the TOP of the map, so the y axis flips.
    def px_to_world(self) -> np.ndarray:
        """3x3 homogeneous (col,row,1) → (wx,wy,1)."""
        res, (ox, oy, _) = self.resolution, self.origin
        return np.array(
            [
                [res, 0.0, ox + 0.5 * res],
                [0.0, -res, oy + (self.h - 0.5) * res],
                [0.0, 0.0, 1.0],
            ]
        )

    def world_to_px(self) -> np.ndarray:
        return np.linalg.inv(self.px_to_world())


# -- registration -----------------------------------------------------------


def _rotate(img: np.ndarray, deg: float) -> np.ndarray:
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), deg, 1.0)
    return cv2.warpAffine(img, m, (w, h))


def _pad_to(img: np.ndarray, h: int, w: int) -> np.ndarray:
    out = np.zeros((h, w), np.float32)
    out[: img.shape[0], : img.shape[1]] = img
    return out


def _phase_corr(a: np.ndarray, b: np.ndarray) -> tuple[tuple[float, float], float]:
    win = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), resp = cv2.phaseCorrelate(a, b, win)
    return (dx, dy), resp


def register(
    moving: np.ndarray, fixed: np.ndarray, coarse_step: float = 1.0
) -> tuple[float, float, float, float]:
    """Find (deg, dx, dy, response) such that rotating `moving` about its
    padded-image center by deg then shifting by (dx, dy) aligns it to `fixed`.
    Scale is fixed at 1 (same resolution)."""
    ph = max(moving.shape[0], fixed.shape[0])
    pw = max(moving.shape[1], fixed.shape[1])
    # room for rotation corners
    side = int(math.ceil(math.hypot(ph, pw)))
    mov = _pad_to(moving, side, side)
    fix = _pad_to(fixed, side, side)

    # coarse sweep, downsampled 4x
    k = 4
    mov_s = cv2.resize(mov, (side // k, side // k), interpolation=cv2.INTER_AREA)
    fix_s = cv2.resize(fix, (side // k, side // k), interpolation=cv2.INTER_AREA)
    best = (0.0, -1.0)  # (deg, response)
    for deg10 in range(0, int(360 / coarse_step)):
        deg = deg10 * coarse_step
        _, resp = _phase_corr(_rotate(mov_s, deg), fix_s)
        if resp > best[1]:
            best = (deg, resp)
    _log(f"coarse: {best[0]:.1f} deg (response {best[1]:.4f})")

    # fine sweep at full res
    best_full = (best[0], 0.0, 0.0, -1.0)
    deg = best[0] - 1.5
    while deg <= best[0] + 1.5:
        (dx, dy), resp = _phase_corr(_rotate(mov, deg), fix)
        if resp > best_full[3]:
            best_full = (deg, dx, dy, resp)
        deg += 0.1
    _log(
        f"fine: {best_full[0]:.2f} deg shift=({best_full[1]:.2f}, "
        f"{best_full[2]:.2f}) px (response {best_full[3]:.4f})"
    )
    return best_full


def pixel_transform(deg: float, dx: float, dy: float, side: float) -> np.ndarray:
    """3x3 (col,row,1) moving→fixed in the padded frame: rotation about the
    padded center followed by the phase-correlation shift."""
    c = side / 2.0
    th = math.radians(-deg)  # getRotationMatrix2D's positive angle is CCW in
    # image coords with y down == CW in math convention; build the same matrix
    cos, sin = math.cos(th), math.sin(th)
    rot = np.array(
        [
            [cos, -sin, c - cos * c + sin * c],
            [sin, cos, c - sin * c - cos * c],
            [0.0, 0.0, 1.0],
        ]
    )
    shift = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy], [0.0, 0.0, 1.0]])
    return shift @ rot


# -- per-robot helpers ------------------------------------------------------


def _resolve_dir(d: Path) -> Path:
    """Allow dirs relative to the repo's maps/ for convenience."""
    d = Path(d)
    return d if d.is_absolute() else (MAPS_DIR / d)


def _robot_id_from_dir(dir_path: Path) -> str:
    """robot_id == the folder name minus the trailing ``_map`` (autoxing-1_map ->
    autoxing-1). This is the adapters.<key> written into map_transforms.yaml."""
    name = Path(dir_path).name
    return name[:-4] if name.endswith("_map") else name


def _find_map_yaml(dir_path: Path) -> Path | None:
    """The occupancy-map yaml inside a robot's map dir, or None if the dir has no
    map yet. If several exist, the lexicographically-last is used (newest export
    by name) with a warning."""
    yamls = sorted(p for p in Path(dir_path).glob("*.yaml"))
    if not yamls:
        return None
    if len(yamls) > 1:
        _log(f"{Path(dir_path).name}: {len(yamls)} yamls present — using "
             f"{yamls[-1].name} (keep one, or rename, to disambiguate).")
    return yamls[-1]


def _onboard_map_names() -> dict[str, str]:
    """robot_id -> onboard_map.name from maps/robots.yaml, so the written
    ``map_name`` matches what the adapter checks at runtime."""
    rp = MAPS_DIR / "robots.yaml"
    try:
        robots = yaml.safe_load(rp.read_text()).get("robots", [])
    except (OSError, yaml.YAMLError):
        return {}
    out: dict[str, str] = {}
    for r in robots or []:
        rid = r.get("robot_id") or r.get("planner_id")
        nm = (r.get("onboard_map") or {}).get("name")
        if rid and nm:
            out[rid] = nm
    return out


def calibrate(
    robot: GeoMap, master: GeoMap, *, robot_map_name: str, master_frame: str
) -> tuple[MapTransform, float, np.ndarray, int]:
    """Register ``robot`` onto ``master`` and return (transform, response,
    pixel_transform, padded_side)."""
    scale_ratio = robot.resolution / master.resolution
    if abs(scale_ratio - 1.0) > 0.01:
        raise SystemExit(f"Resolutions differ ({scale_ratio=}); resample one map first.")
    deg, dx, dy, resp = register(robot.wall_mask(), master.wall_mask())
    if resp < 0.05:
        _log(f"WARNING: weak registration response ({resp:.4f}) — inspect the overlay.")
    side = int(math.ceil(math.hypot(max(robot.h, master.h), max(robot.w, master.w))))
    px_tf = pixel_transform(deg, dx, dy, side)
    # world(robot) → px(robot) → px(master) → world(master).
    world_tf = master.px_to_world() @ px_tf @ robot.world_to_px()
    s, neg_r, tx = world_tf[0]
    r, s2, ty = world_tf[1]
    if abs(s - s2) > 1e-6 or abs(neg_r + r) > 1e-6:
        _log(f"WARNING: composed transform not a clean similarity:\n{world_tf}")
    tf = MapTransform(
        s=float(s), r=float(r), tx=float(tx), ty=float(ty),
        anchors=[f"image-registration (response={resp:.4f})"], mse=None,
        reeman_map={"name": robot_map_name}, autoxing_map={"map_name": master_frame},
        calibrated_at=time.time(),
    )
    return tf, resp, px_tf, side


def _write_overlay(robot: GeoMap, master: GeoMap, px_tf: np.ndarray, side: int, out: Path) -> None:
    """master walls red, robot walls green, overlap black — for visual QA."""
    fix = _pad_to(master.wall_mask(), side, side)
    warped = cv2.warpAffine(_pad_to(robot.wall_mask(), side, side), px_tf[:2], (side, side))
    overlay = np.full((side, side, 3), 255, np.uint8)
    overlay[fix > 0] = (0, 0, 255)
    overlay[warped > 0] = (0, 200, 0)
    overlay[(fix > 0) & (warped > 0)] = (0, 0, 0)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), overlay)
    _log(f"Overlay: {out}  (black=both, red=master only, green=robot only)")


# -- main -------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--master-map-dir",
        type=Path,
        default=MAPS_DIR / "autoxing-1_map",
        help="The master-frame robot's map dir; its robot_id (dir minus _map) is "
        "the identity entry and master_frame in map_transforms.yaml.",
    )
    ap.add_argument(
        "--robot-map-dir",
        dest="robot_map_dirs",
        action="append",
        type=Path,
        help="A robot map dir to register onto the master (repeatable). robot_id "
        "is the folder name minus the _map suffix. Default: reeman-1_map.",
    )
    ap.add_argument(
        "--out-yaml",
        type=Path,
        default=DEFAULT_TRANSFORM_FILE,
        help=f"declarative transform file to merge into (default: {DEFAULT_TRANSFORM_FILE})",
    )
    ap.add_argument(
        "--cache-dir",
        type=Path,
        default=MAPS_DIR / "map_transform" / "out",
        help="Dir for per-robot offline cache (<robot_id>_to_master_tf.json) + overlays "
        "(gitignored).",
    )
    ap.add_argument("--no-save", action="store_true", help="don't write the per-robot cache")
    ap.add_argument("--no-yaml", action="store_true", help="don't write the transform YAML")
    args = ap.parse_args()

    master_dir = _resolve_dir(args.master_map_dir)
    robot_dirs = [_resolve_dir(d) for d in (args.robot_map_dirs or [MAPS_DIR / "reeman-1_map"])]

    onboard = _onboard_map_names()
    master_id = _robot_id_from_dir(master_dir)
    master_yaml = _find_map_yaml(master_dir)
    if master_yaml is None:
        raise SystemExit(f"No .yaml occupancy map in master dir {master_dir}")
    master = GeoMap(master_yaml)
    master_frame = onboard.get(master_id) or master.name
    _log(f"master[{master_id}]: {master.w}x{master.h} res={master.resolution} frame={master_frame!r}")

    for rdir in robot_dirs:
        rid = _robot_id_from_dir(rdir)
        if rid == master_id:
            _log(f"skip {rid!r}: it is the master frame (identity).")
            continue
        robot_yaml = _find_map_yaml(rdir)
        if robot_yaml is None:
            _log(f"skip {rid!r}: no map yet in {rdir.name}/ — export the robot's "
                 f"occupancy map there, then re-run.")
            continue
        robot = GeoMap(robot_yaml)
        robot_map_name = onboard.get(rid) or robot.name
        _log(f"robot[{rid}]: {robot.w}x{robot.h} res={robot.resolution} map_name={robot_map_name!r}")
        tf, resp, px_tf, side = calibrate(
            robot, master, robot_map_name=robot_map_name, master_frame=master_frame
        )
        print(f"[{rid}] {tf.describe()}")
        _write_overlay(robot, master, px_tf, side, args.cache_dir / "maps" / f"{rid}_overlay.png")
        if not args.no_save:
            save_cache(tf, args.cache_dir / f"{rid}_to_master_tf.json")
        if not args.no_yaml:
            write_transform_file(
                args.out_yaml,
                master_frame=master_frame,
                master_key=master_id,
                adapter_key=rid,
                robot_map_name=robot_map_name,
                tf=tf,
                response=resp,
            )
            _log(f"map_transforms.yaml: adapters.{rid} updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
