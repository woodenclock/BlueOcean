#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml"]
# ///
"""Download maps from all robots in robots.yaml then re-run image calibration.

Usage:
    cd maps && uv run get_map_n_transform.py AMAV-X
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

AUTOXING_SCRIPT = REPO_ROOT / "src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean/autoxing/autoxing_bridge/spellbook/download_map.py"
REEMAN_SCRIPT   = REPO_ROOT / "src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean/reeman/reeman_bridge/spellbook/download_maps.py"


def download_robot(robot: dict, repo_root: Path) -> None:
    mfg = robot.get("manufacturer", "").lower()
    onboard = robot["onboard_map"]
    map_name = onboard["name"]
    asset_dir = repo_root / onboard["asset_dir"]
    asset_dir.mkdir(parents=True, exist_ok=True)

    uv_prefix = ["uv", "run", "--no-project", "--with", "rich", "--with", "requests", "--with", "pyyaml"]

    if mfg == "autoxing":
        env = {**os.environ, "AUTOXING_BASE_URL": robot["endpoint"]}
        spellbook_dir = AUTOXING_SCRIPT.parent
        subprocess.run(
            uv_prefix + ["python", str(AUTOXING_SCRIPT), "-c", str(asset_dir / map_name)],
            cwd=spellbook_dir, env=env, check=True,
        )
    elif mfg == "reeman":
        ep = robot["endpoint"]
        base = ep if ep.startswith("http") else f"http://{ep}"
        env = {**os.environ, "REEMAN_BASE_URL": base}
        spellbook_dir = REEMAN_SCRIPT.parent
        subprocess.run(
            uv_prefix + ["python", str(REEMAN_SCRIPT), "-c", str(asset_dir / map_name)],
            cwd=spellbook_dir, env=env, check=True,
        )
    else:
        print(f"  WARNING: unknown manufacturer '{mfg}', skipping")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <map-dir>  (e.g. AMAV-X)")
        sys.exit(1)

    map_dir_name = sys.argv[1]
    maps_root = Path(__file__).resolve().parent
    robots_yaml_path = maps_root / map_dir_name / "robots.yaml"

    if not robots_yaml_path.exists():
        print(f"ERROR: {robots_yaml_path} not found")
        sys.exit(1)

    robots = yaml.safe_load(robots_yaml_path.read_text())["robots"]
    print(f"Map dir : {map_dir_name}")
    print(f"Robots  : {[r['robot_id'] for r in robots]}\n")

    for robot in robots:
        print(f"Downloading {robot['robot_id']} ({robot.get('manufacturer', '?')})...")
        try:
            download_robot(robot, REPO_ROOT)
        except subprocess.CalledProcessError as e:
            print(f"  ERROR: script exited {e.returncode}")
        except Exception as e:
            print(f"  ERROR: {e}")

    # Image calibration
    master_map_dir = Path(robots[0]["onboard_map"]["asset_dir"]).name
    robot_map_dirs = [Path(r["onboard_map"]["asset_dir"]).name for r in robots[1:]]

    cmd = [
        "uv", "run", "--no-project",
        "--with", "opencv-python-headless",
        "--with", "numpy",
        "--with", "nudged",
        "--with", "pyyaml",
        "--with", "requests",
        "python", "-m", "map_transform.image_calibrate",
        "--map-id", map_dir_name,
        "--master-map-dir", master_map_dir,
    ]
    for d in robot_map_dirs:
        cmd += ["--robot-map-dir", d]

    print(f"\nRunning calibration...")
    subprocess.run(cmd, cwd=maps_root, env={**os.environ, "PYTHONPATH": "."}, check=False)
    print("\nDone.")


if __name__ == "__main__":
    main()
