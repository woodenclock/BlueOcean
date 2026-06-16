# GOAL (dry run v1)

**One API call to the Scheduler ⇒ two VDA5050 order JSONs published on MQTT.**
No real robots, no ROS, no CBS — hardcoded BFS paths are fine. Prove the pipe:

```
send_mapf_schedule.py ──HTTP──▶ Scheduler ──AMQP Schedule──▶ Task Orchestrator
  ──GoToNode amr_mapf TaskRequest (AMQP)──▶ mapf-vda5050 bridge
  ──VDA5050 order──▶ MQTT uagv/v2/{mfg}/{sn}/order   (+ TaskStatus back so GoToNode completes)
```

Done when: scheduler + brokers up + `python3 send_mapf_schedule.py` ⇒ `mosquitto_sub -t 'uagv/#'` shows both robots' orders.

---

# DEMO CHANGED (2026-06-10) — new scheduler stack

`src/rmf2_scheduler_gametl` was replaced with the upstream `rmf2_scheduler` repo:

- **`rmf2_scheduler_server_py` is gone.** The server is now `rts_demo_server`
  (`src/rmf2_scheduler_gametl/rmf2_scheduler_py/apps/rts_demo_server/src/rts_demo_server/app.py`).
- **Scheduler runs from its own compose**, not the umbrella one:
  `cd src/rmf2_scheduler_gametl && docker compose up -d` → port **8089**
  (the umbrella `docker-compose.yml` now has scheduler/task-orchestrator/res-mapf/vda5050/ui all commented out; only the brokers remain).
- **Port is 8089 everywhere now** (old docs said 8000). The image CMD served on
  8000 while compose mapped 8089→8089 — fixed by a `command:` override in
  `src/rmf2_scheduler_gametl/docker-compose.yaml`.
- **OrbStack networking:** the Docker daemon runs on the Mac, so from this
  Ubuntu machine `localhost:8089` is unreachable. Use
  `python3 send_mapf_schedule.py --host rmf2_scheduler.orb.local`
  (plain `localhost` only works when run from the Mac).
- `/schedule/edit/batch` still exists (`rmf2_scheduler_py/packages/rmf2_scheduler_fastapi/src/rmf2_scheduler_fastapi/endpoints/schedule.py`)
  and accepts the same TASK_ADD/PROCESS_ADD payload — verified 2026-06-10, dry run + real POST both HTTP 200.
- New upstream seed script: `src/rmf2_scheduler_gametl/scripts/seed_demo_schedule.py` (Gantt demo data, targets `localhost:8089`).
- `demo-readme.md` still documents the old port-8000 umbrella-compose flow — stale.

---

# MEGA PLAN — phases (top-down)

## Phase 0 — Baseline sanity (nothing new, just verify)
- [x] Scheduler up: `cd src/rmf2_scheduler_gametl && docker compose up -d` (port 8089, healthy 2026-06-10)
- [x] `python3 send_mapf_schedule.py --host rmf2_scheduler.orb.local --dry-run` returns 2xx (API + storage path verified 2026-06-10)
- [ ] Brokers up: `docker compose up -d amqp-broker mqtt-broker` (umbrella compose; both exited — restart needed)
- [ ] Re-enable `task-orchestrator` in the umbrella `docker-compose.yml` (currently commented out)
- [ ] Prove the orchestrator→workflow path with the shipped demo: `python3 fixtures/send_schedule.py` → orchestrator logs "Received AMQP workflow execute"
- [ ] Keep `mosquitto_sub -h localhost -t '#' -v` + RabbitMQ mgmt UI (localhost:15672) open as the dashboard

## Phase 1 — Scheduler fires → AMQP `Schedule` message  ← **DONE via demo endpoint (2026-06-10)**
Implemented as **`POST /demo/blue-ocean`** on the scheduler's FastAPI app
(`rts_demo_server/src/rts_demo_server/blue_ocean.py`): dry-run robot locations
(autoxing `0,1`→`3,0`, reeman `5,2`→`4,0`, source `maps/gametl_demo.lif.yaml`),
then publishes **one Schedule message per robot** (plan B from 2.1 — separate
workflows so both GoToNodes run in parallel) to `@RECEIVE@` on
`$AMQP_HOST:$AMQP_PORT` (default `amqp-broker:5672`). `dry_run=false` → 501
until live robot location APIs are wired. `pika` added to `rts_demo_server`;
scheduler standalone compose now joins the umbrella `rmf2_demo_gametl_rmf2-net`
network (umbrella brokers must be up first).
- [ ] 1.1 (future, real stack) Wire a `TaskExecutorManager` + `ProcessExecutor` in `rts_demo_server/app.py` (signature: `rmf2_scheduler_py/packages/rmf2_scheduler_fastapi/src/rmf2_scheduler_fastapi/scheduler.py:82`)
- [ ] 1.2 (future, real stack) Implement a task executor for `type: custom/go_to_amr` so stored schedules fire automatically (the demo endpoint bypasses scheduler storage)
- [x] 1.3 Publish to AMQP fanout exchange `@RECEIVE@` — done in `/demo/blue-ocean`; `pika` added to the scheduler image
- [x] 1.4 Direct-AMQP fallback — superseded by `/demo/blue-ocean` (press it in Swagger at `:8089/docs`)
- [x] ✅ Verify: `curl -X POST http://localhost:8089/demo/blue-ocean` → orchestrator log shows both workflows received (2026-06-10)

## Phase 2 — Orchestrator runs the GoToNode workflow
Orchestrator already consumes `Schedule` and runs crossflow diagrams (`workflow_executor/src/executor/amqp_handlers.rs`); `GoToNode` publishes an `amr_mapf` `TaskRequest` to `@RECEIVE@` and blocks on a `TaskStatus` reply (`workflow_executor/src/nodes.rs:336`).
- [x] 2.1 Diagram shape settled: plan B — `/demo/blue-ocean` sends 2 independent Schedule messages, each a one-node GoToNode diagram (no fork needed)
- [x] 2.2 NOT needed for dry run: grid nodes absent from `location_coord_map_res.json` pass through `coord_map.get(...).unwrap_or(raw)` (`nodes.rs:368`), so the bridge receives raw grid IDs (`3,0`) — exactly what its BFS keys on. Adding real `(x,y)` values belongs to phase 5 (would break the dry-run bridge's grid-ID matching).
- [x] ✅ Verify: 2 `TaskRequest` (`amr_mapf`, correct `robot_id`/`goal_location`) seen on `@RECEIVE@` — consumed by the bridge, paths logged (2026-06-10)

## Phase 3 — `amr_mapf` TaskRequest → VDA5050 order on MQTT (the missing service)
**REPLACED 2026-06-10 (same day):** the BFS bridge `src/mapf_vda5050_bridge/` was deleted; the `mapf-planner` service (real CBS stack, see 5.1) now owns the AMQP TaskRequest → plan → VDA5050 order + TaskStatus flow. Contract notes below remain valid (the planner implements the same envelope):
- [x] 3.1 AMQP consumer: durable queue `@RECEIVE@-mapf-bridge` bound to the `@RECEIVE@` fanout, filtering `type == "TaskRequest" && taskType == "amr_mapf"` (camelCase, matching GoToNode's serde renames)
- [x] 3.2 Path = BFS over `maps/gametl_demo.lif.yaml` (nodes/edges/blocked_edges/robot starts) instead of hardcoded lists — verified it yields Autoxing `0,1→1,1→2,1→3,1→3,0`, Reeman `5,2→5,1→4,1→3,1→3,0→4,0`
- [x] 3.3 Order JSON modeled on `fixtures/publish_mqtt_route.py` (nodes even/edges odd sequenceIds, `released: true`, nodePosition from grid coords, `orderUpdateId: 0`)
- [x] 3.4 Publishes to `uagv/v2/Autoxing/A001/order` (autoxing; was Manufacturer/S001 until 2026-06-11) and `uagv/v2/Reeman/R001/order` (reeman)
- [x] 3.5 Replies `TaskStatus` `COMPLETED` (or `ERROR` on no-path) on `@RECEIVE@` with id `urn:ngsi-ld:Task:{uuid}:TaskStatus` — the orchestrator response listener (`amqp.rs:298`) trims `:TaskStatus` and unblocks the GoToNode waiter
- [x] 3.6 Service already in `docker-compose.mapf-demo.yml` (`mapf-vda5050-bridge`); res-mapf stays disabled in the dry-run path
- [x] ✅ Verify: full chain green 2026-06-10 — `POST /demo/blue-ocean` → orchestrator workflows completed → `fixtures/verify_orders.py` OK for both robots

## Phase 4 — Single-trigger E2E dry run — **SKIPPED (2026-06-10)**: Swagger `POST /demo/blue-ocean` is the trigger; no fake-send script wanted
- [x] 4.1 One command up: mapf-demo overlay merged into the main `docker-compose.yml` (2026-06-11) — `docker compose up --build`
- [ ] 4.2 One trigger: `python3 send_mapf_schedule.py --host rmf2_scheduler.orb.local --start-delay 5` (port defaults to 8089)
- [x] 4.3 Verification script (`fixtures/verify_orders.py`): subscribe `uagv/#`, assert both orders arrive with the expected node sequences, exit 0/1 — passing 2026-06-10
- [ ] 4.4 Update `demo-readme.md` with the exact 3-command run sequence

## Phase 5 — After the dry run (real stack, in order)
- [~] 5.1 Real MAPF (planning proven 2026-06-10, no ROS): `src/res_mapf_gametl/res_mapf/examples/blue_ocean_mapf_demo.py` runs the real stack (`MAPFCoordinator` + CBS + `PlanGenerator`) on the constrained graph via a `MapConstrainedEnvironment` (CBS `Environment` subclass enforcing LIF allowed/blocked edges). CBS resolves the `3,1`/`3,0` conflict: reeman goes first, autoxing waits at `2,1` with `departure_blockers` (depart `2,1` when reeman progress ≥ 4.0 i.e. at `3,0`; depart `3,1` when ≥ 5.0 i.e. at `4,0`). One-shot compose service `mapf-planner` (`docker/mapf-planner.Dockerfile`, uv, no pybullet/ROS) logs the plans as DEBUG JSON + rich pprint. DONE same day: `examples/blue_ocean_planner_service.py` is the long-running replacement for the bridge — consumes `amr_mapf` TaskRequests, replans ALL known tasks on each arrival (incremental: solo plan v1 for first robot, coordinated v2 when the second arrives), publishes VDA5050 orders + TaskStatus. Verified E2E via `POST /demo/blue-ocean` + `fixtures/verify_orders.py` (both OK). DONE 2026-06-11: planner now POSTs each robot's plan (waypoint coords + `departure_blockers`) to the VDA5050 master REST API (`POST /plans/mapf` on `example_master_webserver.py`) instead of publishing VDA5050 orders to MQTT itself
- [~] 5.1b **Scope change 2026-06-11** — planner no longer talks MQTT; the VDA5050 master owns robot dispatch:
  - [x] Planner -> master REST: `POST /plans/mapf` carries robot_id, manufacturer/serial, order_id, map_id, plan_version, task_id, waypoints (name, x, y) + departure_blockers
  - [x] Master general plan-intake endpoint (`/plans/mapf` POST + GET) stores latest plan per robot, logs it, does NOT dispatch to AGVs yet
  - [x] Master dispatch path (dry-run flavor, 2026-06-11): `/plans/mapf` now builds a VDA5050 order and dispatches via `master.assign_order` in raw planner-frame coords; master loads `gametl_demo_map.json` (generated from the LIF graph, both edge directions, blocked 4,1–4,0 omitted; env `MASTER_MAP_FILE`); both AGVs onboarded at startup; compose runs `autoxing-adapter` + `reeman-adapter` always-on in `--dry-run` (env-configurable client: VDA5050_MANUFACTURER/SERIAL/MAP_ID, HOME_MAP_PATH, HOME_NODE_ID) which teleport pose node-by-node and report node_reached. NOTE 2026-06-12: legacy `/orders/route` + `large_artc_map.json` were REMOVED (master frame is "From Mapping 40" now; plan dispatch goes via `/plans/mapf` only)
  - [~] **Map unification in the master (blocker for REAL-robot dispatch)** — framework done 2026-06-12, coords pending: master now re-resolves order coords by node name from MASTER_MAP_FILE (planner stays grid-frame); real profile loads `gametl_demo_map.real.json` (map_id "From Mapping 40" = autoxing master frame, coords measured per `docs/real-demo-node-coords.md`); reeman adapter gets `MAP_TF_MODE=static` (MAP_TF_STATIC_TX/TY/THETA, default identity). REMAINING: measure the 9 node coords + reeman offset
  - [x] **Real topology is SEPARATE from the dry run (2026-06-12)**: ARTC layout from the hand sketch — `maps/gametl_demo_real.lif.yaml` (10 nodes: 7-node corridor, branch 3,0→2,0, reeman stub 6,2; no blocked edges) + `gametl_demo_map.real.json` (real "From Mapping 40"-frame coords, table in `docs/real-demo-node-coords.md`). `mapf-planner-real` plans on it; scheduler goals per mode in `blue_ocean_robots.json` (real: autoxing→3,0, reeman→2,0)
  - [x] **Real demo mode (2026-06-12)**: `docker compose --profile real-demo up --build` (dry-run profile is the .env default) → vda5050-real + *-adapter-real (no --dry-run, VDA5050_MAP_ID="From Mapping 40"). Scheduler `dry_run=false` no longer 501: reads master `/state`, snaps pose to nearest `/map` node (SNAP_MAX_DIST_M), fixed goals. `start_location` now threaded scheduler → orchestrator (nodes.rs AmqpTaskConfig) → planner (re-seeds agent per TaskRequest; LIF starts remain fallback)
  - [ ] Departure_blocker enforcement in the master (currently stored with the plan but orders go out fully `released`; enforce via `released` horizon held until blocker progress met — merges with 5.2 stitching)
  - [ ] Re-point verification: `fixtures/verify_orders.py` watches `uagv/#` on MQTT — orders flow again now (master-dispatched), but expected order shape changed (assign_order pre-flight, master headers); re-verify or switch to `GET /plans/mapf`
- [ ] 5.2 Order stitching (now master-side): `released` horizon + `orderUpdateId++` on `lastNodeSequenceId` progress (subscribe `.../state`)
- [ ] 5.3 Real Autoxing adapter (`example_autoxing_client.py` against compose broker), then Reeman clone — receives orders from the master, not the planner
- [ ] 5.4 Optional: swap bridge internals for the ROS `res_mapf` stack (fix `res-mapf.Dockerfile` rosdep) without changing the AMQP/REST contract

Granular checklist (A–I items): **[demo-todos.md](./demo-todos.md)** — phase mapping: P1≈C2+D1, P2≈D2+A1–A3, P3≈E1+B3+G2+C4, P4≈I1–I2, P5≈F+G3–G5+H.

---

- [x] **Single-robot movement check (2026-06-12)**: scheduler now has `GET /demo/nodes` (master /map node ids + master-frame coords) and `POST /demo/navigate-to` (`robot_id` + either `goal_node` or master-frame `x`/`y` snapped to the nearest node; `dry_run` defaults false → start = live /state pose snap). Same pipeline as blue-ocean but one robot, one goal. Verified E2E in dry-run for both robots (orders on MQTT, adapters walked, workflows completed). Fixed along the way: dry-run `reeman-adapter` compose env was missing `VDA5050_MAP_ID: gametl_demo`, so its state reported the real-demo map and the master rejected its orders (map mismatch).
- [x] **LargeARTC fully removed (2026-06-12)**: legacy `/orders/route` endpoint + `large_artc_map.json` + `publish_autoxing_l300_route.py` deleted from demo-june-blue-ocean (archived copies remain in `autoxing-l300/`); all defaults/docs/frames now say "From Mapping 40".

# Backlog / notes

- [~] get the mapping from both robot and TF them into the main map
  - [x] **Per-robot map assets pulled (2026-06-12)** — `demo-june-blue-ocean/{autoxing_map,reeman_map}/`, each an image + ROS `map_server` yaml (origin/resolution from the AutoXing map-detail API; Reeman from the carved export). All at default 0.05 m/px.
    - autoxing_map: `autoxing_map_1095x1045.{png,yaml}` — map id **27 "From Mapping 40"** (`192.168.68.64:8090/maps/27.png`), origin `[-37.5, -19.0, 0.0]`. RESOLVED 2026-06-12: "From Mapping 40" IS the master frame everywhere now (robots.json, compose, real map json); all LargeARTC references removed.
    - reeman_map: `reeman_map_1526x1259.{png,yaml}` — `886d…` hash map, origin `[-22.7551, -34.6423, 0.0]` (matches reeman_1 onboard_map).
  - [ ] **NEXT — run it / get robots moving:** dry-run adapters (`python3 example_{autoxing,reeman}_adapter_client.py --dry-run`) → set `CONSTANTS.yml` robot IPs → Reeman↔AutoXing frame calibration (≥3 identically-named waypoints, `AUTOXING_BASE_URL` set; else `MAP_TF_ALLOW_IDENTITY=1`) → real adapters → master webserver (`uv run example_master_webserver.py`, :8000/docs) → single-move sanity (`python3 -m autoxing_bridge.navigate_node 1.0 2.0 0.0`).
- see how MAPF works output the waypoints
- export map/topology PNG from `payload.drawio` (for README/demo docs)
- keep node/edge source of truth in `maps/gametl_demo.lif.yaml`
- if downstream tools require a real LIF schema, translate `maps/gametl_demo.lif.yaml` into that format

Full implementation checklist: **[demo-todos.md](./demo-todos.md)**

Goal 
- a msg sent to the schedule via API to have a schedule. 2 robots move to 
- POST example from repo root: `python3 send_mapf_schedule.py --host rmf2_scheduler.orb.local` (port 8089; `--host localhost` only from the Mac)
- compose: `docker compose up --build` (mapf-demo overlay merged into main `docker-compose.yml` 2026-06-11)

Nodes in the map
0,1 (Auotxing Starting Point)
1,1
2,1
3,1 (intersection)
4,1
5,1
3,0 (Auotxing End Point) (Reeman will have to pass this)
4,0 (Reeman End Point)
5,2 (Reeman Starting Point)

Allowed edges
0,1 -- 1,1
1,1 -- 2,1
2,1 -- 3,1
3,1 -- 4,1
4,1 -- 5,1
3,1 -- 3,0
3,0 -- 4,0
5,2 -- 5,1

Blocked edge
4,1 -- 4,0
