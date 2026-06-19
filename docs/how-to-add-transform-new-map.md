# How to transform a new map to the AutoXing master

> ARES PRIVATE — internal demo data; don't paste live robot IPs/addresses here.

When the Reeman robot is re-mapped, recompute its transform to the master frame
(AutoXing "From Mapping 40") and regenerate `maps/map_transforms.yaml` — the
single source of truth read at adapter init (`MAP_TF_MODE=file`).

## Files to change

- `maps/<robot_id>_map/<new>.{png,yaml}` — drop in the new occupancy grid (0.05 m/px).
The folder name minus `_map` IS the robot_id / adapter key (e.g. `reeman-1_map`).
- `maps/map_transforms.yaml` — the calibrator **merges** this robot's
`adapters.<robot_id>` entry (other adapters are preserved, not clobbered).
- `maps/robots.yaml` — set the robot's `onboard_map.name`/`alias` to the new map (the calibrator reads it from here, so `map_name` always matches).

## Steps

1. **Export the map** from the robot (`get_map_overlays` → `YAML + PNG`) and copy
  both into `maps/reeman-1_map/` (its `<robot_id>_map` dir). Set the active map
   name (the hash) in `maps/robots.yaml` under that robot's `onboard_map.name`.
2. **Calibrate** — run from `maps/` (ephemeral deps via `uv`); writes a per-robot
  overlay + cache to `map_transform/out/` (gitignored) and merges the YAML. The
   master frame is one robot's map dir; every other `--robot-map-dir` is registered
   onto it and gets its own `adapters.<robot_id>` entry:

```bash
cd /Users/game/GLab/rmf2-blue-ocean-stack/maps && PYTHONPATH=. uv run --no-project --with opencv-python-headless --with numpy --with nudged --with pyyaml --with requests python -m map_transform.image_calibrate --master-map-dir autoxing-1_map --robot-map-dir reeman-1_map --robot-map-dir reeman-2-blue_map
```

   robot_id (the `adapters.<key>`) is derived from each folder name (strip `_map`);
   `map_name` is read from `maps/robots.yaml`. Other adapters in the file are kept.

1. **Review** `map_transform/out/maps/<robot_id>_overlay.png` — black = walls
  overlap (good), red = master only, green = robot only. Check `response` ≥ 0.05
   (higher is better). Re-export and re-run if walls don't line up.
2. **Commit** the tracked files (`maps/robots.yaml`, `maps/map_transforms.yaml`,
  the new map png/yaml); `map_transform/out/` is gitignored.
3. **Apply** (maps are mounted, no rebuild):
  ```bash
   docker compose --profile real-demo up -d vda5050-real
  ```

## How a transform is defined

```yaml
master_frame: From Mapping 40            # AutoXing onboard map = master = identity
adapters:
  reeman:
    map_name: 1fa43762ca0bec4a673fb45d2dd544e8   # must match robots.yaml + the robot's active map
    robot_to_master: {tx: 1.3245, ty: 1.9888, theta: 3.090978, scale: 1.0}  # metres, radians, ~1.0
    source: image-registration
    response: 0.2738                     # phase-correlation confidence (0–1)
```

## Gotchas


| Symptom                                  | Fix                                                                    |
| ---------------------------------------- | ---------------------------------------------------------------------- |
| "Resolutions differ" abort               | Re-export the grid at 0.05 m/px.                                       |
| Weak `response`, walls don't overlap     | Re-export a cleaner map; inspect the overlay.                          |
| Adapter rejects the transform at runtime | `onboard_map.name` in `robots.yaml` must match the robot's active map. |
| New transform not applied                | Restart `vda5050-real` (step 5).                                       |


**Adding a new robot:** create `maps/<robot_id>_map/` with its exported map, add the
robot to `maps/robots.yaml` (with `onboard_map.name`), then pass
`--robot-map-dir <robot_id>_map` to the calibrator. robot_id (the `adapters.<key>`)
is derived from the folder name, the entry is merged (others preserved), and the
real adapter defaults `MAP_TF_ADAPTER` to its own robot_id — so no code change is
needed for a 3rd+ robot.