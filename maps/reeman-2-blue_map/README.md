# reeman-2-blue_map — onboard map for `reeman-2-blue` (R002)

> ARES PRIVATE — internal demo data; don't paste live robot IPs/addresses here.

This directory holds the onboard occupancy map exported from the **second Reeman
robot** (`robot_id: reeman-2-blue`, `serial_number: R002`). It is referenced by
`maps/robots.yaml` → the `reeman-2-blue` entry's `onboard_map.asset_dir`.

The folder name is `<robot_id>_map`; the calibrator derives the map_transforms
adapter key by stripping the `_map` suffix (→ `reeman-2-blue`).

## TODO before the real demo

1. Export the map from the robot (`get_map_overlays` → PNG + YAML, 0.05 m/px) and
   drop both files here, e.g. `reeman2_map_<WxH>.{png,yaml}`.
2. Set the immutable map hash + robot host in `maps/robots.yaml` (single source of
   truth): the `reeman-2-blue` entry's `onboard_map.name` and `endpoint`.
3. Calibrate every robot's frame to the AutoXing master in one shot (writes one
   `adapters.<robot_id>` entry per robot map dir, master frame = autoxing-1):
   ```bash
   cd maps
   PYTHONPATH=. uv run --no-project \
     --with opencv-python-headless --with numpy --with nudged --with pyyaml --with requests \
     python -m map_transform.image_calibrate \
     --master-map-dir autoxing-1_map \
     --robot-map-dir reeman-1_map \
     --robot-map-dir reeman-2-blue_map \
     --out-yaml map_transforms.yaml
   ```

Dry-run does not need these assets (the simulated adapter doesn't switch maps).
See `docs/how-to-add-transform-new-map.md`.
