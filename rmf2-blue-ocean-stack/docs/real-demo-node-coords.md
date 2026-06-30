# Real demo — ARTC node coordinates (AutoXing "l1-artc" frame)

> ARES PRIVATE — internal demo data.

The real demo runs on its **own topology**, separate from the dry-run grid:
`maps/<VDA5050_MAP_ID>/real.layout.lif.json` (loaded and served by the VDA5050 master).
Coordinates below were read from the hand-measured sketch (`ARTC.heic`,
2026-06-12) of the AutoXing map.

When adding nodes, every edge must connect grid ids that differ by ±1 in column
or row (e.g. `0,3`→`1,3`→`2,3`, not `0,3`→`2,3`). Skipping ids breaks CBS/MAPF.
See [`how-to-add-node-to-map.md`](./how-to-add-node-to-map.md#mapf--cbs-grid-rules-read-this-first).

```
0,1 - 1,1 - 2,1 - 3,1 - 4,1 - 5,1 - 6,1
  |                                 |
0,2 - 0,3 - 1,3 - 2,3 - 3,3 - 4,3 - 5,3 - 6,3
              |       |       |
            2,4     3,4     6,2
                   |                 |
            2,0 - 3,0
```

| node_id | real x [m] | real y [m] | role |
|---------|-----------:|-----------:|------|
| 0,1 | -5.0 | -7.0 | AutoXing start |
| 0,2 | -12.35 | -7.0 | corridor (0,1 ↔ 0,3) |
| 0,3 | -19.7 | -7.0 | ARTC entrance |
| 1,3 | -19.7 | -1.3 | corridor (0,3 ↔ 2,3) |
| 2,3 | -19.7 | 4.4 | Human Zone Arm road |
| 2,4 | -21.3 | 4.4 | Human Zone Arm rack |
| 3,3 | -19.7 | 6.8 | Human Zone TV road |
| 3,4 | -21.3 | 6.8 | Human Zone TV rack |
| 4,3 | -19.7 | 12.63 | corridor (3,3 ↔ 6,3) |
| 5,3 | -19.7 | 18.47 | corridor (3,3 ↔ 6,3) |
| 6,3 | -19.7 | 24.3 | End hallway |
| 1,1 | -4.15 | -2.0 | corridor |
| 2,1 | -4.15 |  3.0 | corridor |
| 3,1 | -4.15 |  6.0 | intersection |
| 4,1 | -4.2 |  9.0 | corridor |
| 5,1 | -4.4 | 16.0 | corridor |
| 6,1 | -4.4 | 23.7 | corner |
| 6,2 | -9.0 | 23.7 | Reeman start |
| 3,0 |  0.0 |  6.0 | AutoXing goal (Reeman passes through) |
| 2,0 |  0.0 |  2.0 | Reeman goal |

To change a coordinate: edit `maps/<VDA5050_MAP_ID>/real.layout.lif.json`, then restart
the master — `docker compose --profile real-demo up -d vda5050-real`
(no rebuild needed; `maps/` is mounted). The node id `"col,row"` encodes the
planner grid; `x`/`y` are the metric master-frame coords the master dispatches.

Pre-run checklist:

- [ ] The VDA5050 `map_id` **"l1-artc"** comes from `map.id` in
      `maps/<VDA5050_MAP_ID>/real.layout.lif.json`; the adapters fetch it from the master
      `/map` (override with `VDA5050_MAP_ID`). At startup each adapter switches
      its robot to its `onboard_map` from the master `/robots` —
      `maps/autoxing-1_map/` (AutoXing id 27) or `maps/reeman-1_map/` (Reeman hash
      `1fa43762ca0bec4a673fb45d2dd544e8`). Make sure each robot is localized
      on its map.
- [ ] If the two robots' map frames do not coincide, set the Reeman static
      offset via `MAP_TF_STATIC_TX` / `MAP_TF_STATIC_TY` / `MAP_TF_STATIC_THETA`
      (defaults 0 = identity) on `reeman-adapter-real`.
- [ ] Each robot's REST host set in `maps/<VDA5050_MAP_ID>/robots.yaml` (`endpoint` per robot:
      `autoxing-1`, `reeman-1`, `reeman-2-blue`) — the single source of truth.
- [ ] Each robot localized on its onboard map; the scheduler snaps the live
      `/state` pose to the nearest map node at run time (limit `SNAP_MAX_DIST_M`,
      default 3 m). No config start nodes — placement is wherever the robot
      physically is.
