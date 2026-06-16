# Project Blue Ocean Demo

A two-robot Multi-Agent Path Finding (MAPF) and VDA5050 coordination demo. A
single API call schedules two heterogeneous robots (AutoXing, Reeman) to their
goals; a Conflict-Based Search (CBS) planner resolves their path conflict and
dispatches collision-free VDA5050 orders. The stack runs either fully simulated
(**dry run**) or against physical robots (**real demo**) from one
`docker-compose.yml`.

## Prerequisites

Docker with Compose v2. Nested source repos under `src/` must be present (managed
via `vcs import`; `src/` is git-ignored). No host Python is required to run the
stack — only to execute the verification fixtures.

---

## Dry run (simulated, no robots)

The dry-run profile uses simulated adapters that teleport their reported pose
node by node — no hardware needed. It is the default profile (`.env` →
`config/config.env`).

```bash
# 1. Bring the stack up (first build ~2 min for the ROS images)
docker compose --profile dry-run up --build
# (dry-run is also the default profile, so `docker compose up --build` works too)

# 2. Trigger the two-robot demo
curl -X POST 'http://localhost:8089/demo/blue-ocean?dry_run=true'

# 3. Verify both robots received correct VDA5050 orders on MQTT
uv run fixtures/verify_orders.py
```

Prefer a UI? Skip the `curl` in step 2 and trigger the demo from the scheduler's
Swagger page instead — open [http://localhost:8089/docs](http://localhost:8089/docs), expand
`POST /demo/blue-ocean`, click **Try it out**, leave `dry_run` as `true`, and
**Execute**.

Where to watch:

- Scheduler API — [http://localhost:8089/docs](http://localhost:8089/docs)
- VDA5050 master — [http://localhost:8000/docs](http://localhost:8000/docs) (`/state`, `/map`, `/plans/mapf`)
- Dashboard UI — [http://localhost:3000](http://localhost:3000)
- **VDA Visualiser** — [http://localhost:3000/system/vda-visualiser](http://localhost:3000/system/vda-visualiser) (see [below](#vda-visualiser))

The CBS planner sends the two robots through the shared corridor one at a time:
one robot crosses first while the other waits at the intersection, then follows.

**Re-running.** Restart the master and adapters *together* — the master holds
per-robot order state in memory, so adapters restarting alone leave it stale
(orders then come back `STITCH_REJECTED`):

```bash
docker compose restart vda5050 autoxing-adapter reeman-adapter
```

---

## Real demo (physical robots)

alt

The real demo swaps in the `*-real` services and plans on the ARTC topology
(`maps/gametl_demo_real.lif.yaml`), with coordinates in the AutoXing
"From Mapping 40" master frame.

Start and goal nodes (real-world x, y in metres):


| Robot    | Start node (x, y) | Goal node (x, y) |
| -------- | ----------------- | ---------------- |
| AutoXing | `0,1` (−5, −7)    | `3,0` (0, 6)     |
| Reeman   | `6,2` (−9.4, 24)  | `2,0` (0, 2)     |


### Pre-flight

1. Both robots powered, localized on their onboard maps, and physically placed
  near their start nodes (AutoXing → `0,1`, Reeman → `6,2`) — within
   `SNAP_MAX_DIST_M` (3 m) of the node.
2. Robot connectivity set in `config/config-real.env`: `AUTOXING_BASE_URL`
  (e.g. `http://<autoxing-ip>:8090`) and `REEMAN_ROBOT_IP`.

### Run

```bash
# 1. Bring up the real-demo profile
docker compose --env-file config/config.env --env-file config/config-real.env up --build

# 2. Trigger the demo
curl -X POST 'http://localhost:8089/demo/blue-ocean?dry_run=false'
```

Or trigger it from Swagger: open [http://localhost:8089/docs](http://localhost:8089/docs), expand
`POST /demo/blue-ocean`, click **Try it out**, set `dry_run` to `false`, and
**Execute**.

`dry_run=false` reads each robot's live pose from the master's `/state`, snaps it
to the nearest `/map` node as the start, and plans to the goals above.

**What happens.** Reeman crosses the shared branch first; AutoXing holds at the
intersection until Reeman clears `3,0`, then advances to its goal. This ordering
is forced by the layout — AutoXing's goal `3,0` sits on Reeman's only path to
`2,0`, so AutoXing cannot occupy it until Reeman has passed through.

**Errors.** `409` = a robot has no pose, or its pose is farther than
`SNAP_MAX_DIST_M` (3 m) from any node — re-localize or move it closer to its
start node and retry. `502` = the VDA5050 master is unreachable.

See `docs/real-demo-node-coords.md` for the full node table and pre-flight
checklist.

### Map-frame transform

The two robots localize on their own native maps, so AutoXing (the master frame)
and Reeman do not share coordinates. The transforms live in
`src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean/map_transforms.yaml`
— it declares the `master_frame` plus a per-adapter `robot_to_master` similarity
(AutoXing is identity; Reeman is a ~177° + (1.33, 1.99) m offset).
`config-real.env` sets `MAP_TF_MODE=file` so the Reeman adapter reads its entry
at init. Regenerate the file offline from the committed onboard maps (no robots
needed) with:

```bash
cd src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean
./.venv/bin/python -m map_transform.image_calibrate   # rewrites map_transforms.yaml
```

The file is baked into the adapter image, so a rebuild (`up --build`) is needed
after editing it. Unset `MAP_TF_MODE` to fall back to live `nudged` waypoint
calibration against the robots instead.

---

## VDA Visualiser

**System → VDA Visualiser** at [localhost:3000/system/vda-visualiser](http://localhost:3000/system/vda-visualiser).
Live map + robot poses over `ws://localhost:8000/ws/state` (map once, then ~300 ms state).

Nodes are **not** configured in the UI. The visualiser draws the **JSON master
map** the VDA5050 master loads at startup (`MASTER_MAP_FILE`) — same payload as
`GET /map`. The LIF files (`maps/gametl_demo*.lif.yaml`) are planner-only: node
**ids**, edges, and robot start/goal. They do **not** carry coordinates.

**Where x/y metres live:**

| Profile | Coordinate source | Frame |
| ------- | ----------------- | ----- |
| Dry run | `gametl_demo_map.json` | Synthetic grid — id `"col,row"` → `(col, row)` m, not real-world |
| Real demo | `gametl_demo_map.real.json` | Measured ARTC site coords in AutoXing onboard map **"From Mapping 40"** |

The visualiser labels each node with the **x/y from that JSON** (real demo) or the
grid stand-in (dry run). To change a real-world coordinate, edit
`gametl_demo_map.real.json` — not the LIF file.

| Role | Dry run | Real demo |
| ---- | ------- | --------- |
| **VDA master map** (what the visualiser draws) | `src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean/gametl_demo_map.json` (`MASTER_MAP_FILE` default on `vda5050`) | `src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean/gametl_demo_map.real.json` (`MASTER_MAP_FILE` on `vda5050-real`) |
| **MAPF planner graph** (node ids for CBS) | `maps/gametl_demo.lif.yaml` | `maps/gametl_demo_real.lif.yaml` |

### Dry-run nodes (`gametl_demo_map.json`)

**Not real-world** — synthetic 9-node grid; id `"col,row"` → metres `(col, row)`:

```
0,1 - 1,1 - 2,1 - 3,1 - 4,1 - 5,1
                   |
            3,0 - 4,0
                   ^
              5,2 (Reeman stub)
```

| node_id | x [m] | y [m] | role |
| ------- | ----: | ----: | ---- |
| 0,1 | 0.0 | 1.0 | AutoXing start |
| 1,1 | 1.0 | 1.0 | corridor |
| 2,1 | 2.0 | 1.0 | corridor |
| 3,1 | 3.0 | 1.0 | intersection |
| 4,1 | 4.0 | 1.0 | corridor |
| 5,1 | 5.0 | 1.0 | corridor |
| 3,0 | 3.0 | 0.0 | AutoXing goal |
| 4,0 | 4.0 | 0.0 | Reeman goal |
| 5,2 | 5.0 | 2.0 | Reeman start |

Planner-only blocked edge: `4,1` ↔ `4,0` (`blocked_edges` in `maps/gametl_demo.lif.yaml`).

### Real-demo nodes (`gametl_demo_map.real.json`)

**Real-world coordinates** (metres on the AutoXing map at the ARTC site). The
LIF file only names these nodes; every `x`/`y` below is authored in the JSON
(hand-measured sketch → `docs/real-demo-node-coords.md`):

```
0,1 - 1,1 - 2,1 - 3,1 - 4,1 - 5,1 - 6,1
                   |                 |
            2,0 - 3,0               6,2
```

| node_id | x [m] | y [m] | role |
| ------- | ----: | ----: | ---- |
| 0,1 | −5.0 | −7.0 | AutoXing start |
| 1,1 | −4.15 | −2.0 | corridor |
| 2,1 | −4.15 | 3.0 | corridor |
| 3,1 | −4.15 | 6.0 | intersection |
| 4,1 | −4.2 | 9.0 | corridor |
| 5,1 | −4.4 | 16.0 | corridor |
| 6,1 | −4.4 | 23.7 | corner |
| 6,2 | −9.0 | 23.7 | Reeman start |
| 3,0 | 0.0 | 6.0 | AutoXing goal (Reeman passes through) |
| 2,0 | 0.0 | 2.0 | Reeman goal |

```bash
curl -s http://localhost:8000/map | jq '.nodes[] | {node_id, x, y}'
```

Edit **`gametl_demo_map.real.json`** to change real-world coords (+ matching LIF
only if topology/node ids change), then rebuild/restart `vda5050-real`.

---

## Data flow

`POST /demo/blue-ocean` publishes two `Schedule` messages to the AMQP fanout
exchange; the **task-orchestrator** runs each as a `GoToNode` workflow and emits an
`amr_mapf` `TaskRequest`; the **MAPF planner** runs CBS over the LIF map graph,
resolving the two robots' conflict with departure blockers, and POSTs each plan to
the **VDA5050 master**; the master re-resolves node coordinates against its loaded
map and dispatches VDA5050 orders over MQTT to the **robot adapters**, which (in
dry-run) walk the path and report progress, while `TaskStatus` flows back through
AMQP to unblock the workflow.

## Service ports

Defined in `config/config.env`; override via `.env` or `--env-file`.


| Service                  | Port         |
| ------------------------ | ------------ |
| Scheduler API            | 8089         |
| VDA5050 master           | 8000         |
| Task orchestrator        | 2727         |
| MQTT broker              | 1883         |
| AMQP broker / management | 5672 / 15672 |
| UI                       | 3000         |


