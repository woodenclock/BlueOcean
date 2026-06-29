# maps/ — multi-floor map assets + transforms

> ⚠️ **ARES PRIVATE** — internal demo data. Don't paste live robot IPs/addresses,
> credentials, or site details here.

This directory is the single map/transform/robots authority served by the
VDA5050 master. It holds **shared tooling** at the root and **one self-contained
dir per floor**. The active floor is chosen by the `VDA5050_MAP_ID` env var in
the repo-root `.env` (see `.env.sample`) and consumed by `docker-compose.yml`.
`VDA5050_MAP_ID` is both the AutoXing master map id **and** the floor dir name.

```
maps/
├── map_transform/        # shared Python calibration pkg (floor-agnostic)
├── pyproject.toml        # shared tooling deps (uv)
├── uv.lock
├── .venv/                # local, gitignored
├── AMAV-X/               # VDA5050_MAP_ID=AMAV-X  — AMAV-X master frame (default)
└── l1-artc/              # VDA5050_MAP_ID=l1-artc — ARTC real floor
```

Each floor dir uses the **same normalized filenames** so `VDA5050_MAP_ID` is the
only knob the stack needs:

| File | Purpose |
|------|---------|
| `robots.yaml` | per-floor robot roster (identity, endpoints, onboard maps) |
| `map_transforms.yaml` | per-floor robot→master frame transforms |
| `real.layout.lif.json` | VDA5050 LIF topology (nodes, edges, stations) — loaded by the master |
| `master.image.png` | master-frame occupancy image for the UI overlay |
| `master.image.yaml` | resolution/origin meta for `master.image.png` |
| `<robot_id>_map/` | each robot's onboard occupancy map (PNG + yaml) |

`docker-compose.yml` resolves all of these as `/app/maps/${VDA5050_MAP_ID}/<file>`.

## Switching floors

Set `VDA5050_MAP_ID` in `.env` to the floor dir name:

```bash
# AMAV-X (default real demo)
VDA5050_MAP_ID=AMAV-X

# ARTC floor
VDA5050_MAP_ID=l1-artc
```

> Note: `AMAV-X`'s `robots.yaml` has no `routes:` goals yet; `l1-artc` is the
> fully-wired floor with per-robot goal routes.

## Calibrating a floor's transforms

The calibrator registers each robot's onboard occupancy PNG onto the master
frame and writes one `adapters.<robot_id>` entry into that floor's
`map_transforms.yaml`. Pick the floor with `--map-id` (the VDA5050 map id = the
floor dir name); map dirs are then relative to `maps/<map-id>/`:

```bash
cd maps
PYTHONPATH=. uv run --no-project \
  --with opencv-python-headless --with numpy --with nudged --with pyyaml --with requests \
  python -m map_transform.image_calibrate \
  --map-id AMAV-X \
  --master-map-dir autoxing-1_map \
  --robot-map-dir reeman-2-blue_map
```

`map_name` per robot is read from `maps/<map-id>/robots.yaml` →
`onboard_map.name`, so the written transform matches what the adapter checks at
runtime. Dry-run does not need calibration assets (the simulated adapter doesn't
switch maps). See `docs/how-to-add-transform-new-map.md`.

## Adding a robot's onboard map

1. Export the map from the robot (`get_map_overlays` → PNG + YAML, 0.05 m/px) and
   drop both files in `maps/<map-id>/<robot_id>_map/`.
2. Set the immutable map hash + robot host in `maps/<map-id>/robots.yaml`
   (single source of truth): the entry's `onboard_map.name` and `endpoint`.
3. Re-run the calibrator above with an extra `--robot-map-dir <robot_id>_map`.
