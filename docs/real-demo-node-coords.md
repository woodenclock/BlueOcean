# Real demo — ARTC node coordinates (AutoXing "From Mapping 40" frame)

> ARES PRIVATE — internal demo data.

The real demo runs on its **own topology**, separate from the dry-run grid:
planner graph `maps/gametl_demo_real.lif.yaml`, master map
`src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean/gametl_demo_map.real.json`.
Coordinates below were read from the hand-measured sketch (`ARTC.heic`,
2026-06-12) of the AutoXing map.

```
0,1 - 1,1 - 2,1 - 3,1 - 4,1 - 5,1 - 6,1
                   |                 |
            2,0 - 3,0               6,2
```

| node_id | real x [m] | real y [m] | role |
|---------|-----------:|-----------:|------|
| 0,1 | -5.0 | -7.0 | AutoXing start |
| 1,1 | -4.15 | -2.0 | corridor |
| 2,1 | -4.15 |  3.0 | corridor |
| 3,1 | -4.15 |  6.0 | intersection |
| 4,1 | -4.2 |  9.0 | corridor |
| 5,1 | -4.4 | 16.0 | corridor |
| 6,1 | -4.4 | 23.7 | corner |
| 6,2 | -9.0 | 23.7 | Reeman start |
| 3,0 |  0.0 |  6.0 | AutoXing goal (Reeman passes through) |
| 2,0 |  0.0 |  2.0 | Reeman goal |

To change a coordinate: edit `gametl_demo_map.real.json`, then
`docker compose --env-file config/config.env --env-file config/config-real.env up -d --build vda5050-real`.
(The grid ids in the LIF file are planner-only; the master re-resolves
dispatched order coordinates by node id from the JSON map.)

Pre-run checklist:

- [ ] The VDA5050 `map_id` **"From Mapping 40"** is set by `VDA5050_MAP_ID` on both
      real adapters and by `map_info.map_id` in `gametl_demo_map.real.json`.
      At startup each adapter switches its robot to the demo map under
      `autoxing_map/` (AutoXing id 27) or `reeman_map/` (Reeman hash
      `886d396851aa60b150419998b0a56e59`). Make sure each robot is localized
      on its map.
- [ ] If the two robots' map frames do not coincide, set the Reeman static
      offset via `MAP_TF_STATIC_TX` / `MAP_TF_STATIC_TY` / `MAP_TF_STATIC_THETA`
      (defaults 0 = identity) on `reeman-adapter-real`.
- [ ] `AUTOXING_BASE_URL` set for `autoxing-adapter-real`; Reeman spellbook
      active-robot IP configured.
- [ ] Robots placed near their start nodes (AutoXing → `0,1` at (-5, -7),
      Reeman → `6,2` at (-9, 23.7)) and localized (the scheduler snaps the
      live pose to the nearest node, limit `SNAP_MAX_DIST_M`, default 3 m).
