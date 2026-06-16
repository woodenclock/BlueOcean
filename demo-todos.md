# Two-Robot MAPF Demo — Implementation Todos

Autoxing + Reeman schedule via Scheduler → Orchestrator → MAPF → MQTT orders.

**VDA5050 “master” pattern in this repo** (no separate Master REST service):

| Role | Script | MQTT topic |
|------|--------|------------|
| Master (order publisher) | `src/vda5050_core_gametl/vda5050_core_py/autoxing-l300/publish_autoxing_l300_route.py` | `uagv/v2/Manufacturer/S001/order` |
| AGV adapter | `src/vda5050_core_gametl/vda5050_core_py/autoxing-l300/example_autoxing_client.py` | subscribes order, publishes `.../state` |
| Robot I/O | `autoxing_bridge/` | Autoxing REST `/chassis/moves` + pose poll |

Flow: publish order → adapter `on_navigate` → `dispatch_move` → `node_reached` → C++ advances horizon.

Design reference: `payload.drawio` · Map spec: `todo.md`

---

## Goal

Send a schedule via the Scheduler API so **two robots** move in parallel:

- **Autoxing:** `0,1` → `3,0`
- **Reeman:** `5,2` → `4,0` (must pass `3,0`; no edge `4,1` → `4,0`)

---

## Map topology

### Nodes

| Node | Role |
|------|------|
| `0,1` | Autoxing start |
| `1,1`, `2,1` | Corridor |
| `3,1` | Intersection (shared) |
| `4,1`, `5,1` | Corridor |
| `3,0` | Autoxing end · Reeman must pass |
| `4,0` | Reeman end |
| `5,2` | Reeman start |

### Allowed edges

```
0,1—1,1—2,1—3,1—4,1—5,1
3,1—3,0
3,0—4,0
5,2—5,1
```

### Constraints

- **No** `4,1` → `4,0`
- Reeman reaches `4,0` only via `3,0`

### Verified paths (BFS)

- **Autoxing:** `0,1 → 1,1 → 2,1 → 3,1 → 3,0`
- **Reeman:** `5,2 → 5,1 → 4,1 → 3,1 → 3,0 → 4,0`

### MAPF conflict

If both move simultaneously: vertex conflict at `3,1` (t=3) and `3,0` (t=4). Stagger Reeman (+5 timesteps) or use `departure_blockers` at shared nodes.

---

## A. Map & coordinates

- [ ] **A1** — Define grid node → real-world `(x, y, mapId)` lookup for Autoxing (`From Mapping 40` master map)
- [ ] **A2** — Same lookup for Reeman (manufacturer, serial, map, coordinates)
- [ ] **A3** — Machine-readable edge list (allow `3,0→4,0`, block `4,1→4,0`)
- [ ] **A4** — TF / frame alignment so scheduler goals like `3,0` resolve to VDA5050 `nodePosition`

---

## B. MAPF output → VDA5050 order shape

- [ ] **B1** — Trace MAPF `Plan` waypoints: `name`, `position`, `departure_blockers` (not `released`)
- [ ] **B2** — Map `DependencyManager` dispatchable waypoints → VDA5050 `released: true/false` (horizon ≈ `max_enqueued=2`)
- [ ] **B3** — Order JSON generator modeled on `publish_autoxing_l300_route.py`:
  - `nodes[]` with `nodeId`, `sequenceId`, `released`, `nodePosition`
  - `edges[]` between consecutive nodes
  - `orderId` / `orderUpdateId` for stitching (see `order_stitcher.cpp`)
- [ ] **B4** — Shared nodes `3,1`, `3,0`: keep Reeman nodes `released: false` until Autoxing clears

---

## C. Infrastructure (compose must run)

- [ ] **C1** — Scheduler Dockerfile: `CMD` → `rmf2_scheduler_server_py --host 0.0.0.0`
- [ ] **C2** — Wire scheduler `ProcessExecutor` + task executor (both are `None` in `app.py` today)
- [ ] **C3** — Fix `res-mapf` image: install `uv` Python packages (`res_mapf_planning`, `res_plan_server`, `res_plan_execution`)
- [ ] **C4** — Add `plan_executor_node` to compose (or thin MQTT publisher node)
- [ ] **C5** — Fix `vda5050` service CMD (no `adapter.launch.py`; use `example_autoxing_client.py` or equivalent)

---

## D. Scheduler → Orchestrator

- [ ] **D1** — Task executor publishes `Schedule` to AMQP `@RECEIVE@` with parallel `GoToNode` fork:
  - Autoxing: `robot_id=autoxing`, goal `3,0`
  - Reeman: `robot_id=reeman`, goal `4,0`
- [ ] **D2** — Fixture `fixtures/send_mapf_schedule.py` (two-robot GoToNode, not MANIP1/SNS1)
- [ ] **D3** — Dashboard / API batch payload for same schedule (P1 in `payload.drawio`)

---

## E. Orchestrator → MAPF (AMQP ↔ ROS bridge)

- [ ] **E1** — AMQP consumer for `TaskRequest` / `task_type: amr_mapf` (orchestrator only consumes `Schedule` today)
- [ ] **E2** — Bridge: AMQP TaskRequest → ROS `/<robot_id>/task_request`
- [ ] **E3** — Bridge: ROS `/fleet/task_status` → AMQP `TaskStatus` (GoToNode waits on this)
- [ ] **E4** — Robot onboard: `/robot_onboard` for `autoxing@0,1` and `reeman@5,2` before tasks

---

## F. MAPF solver / graph

- [ ] **F1** — Replace CBS open `7×7` grid with constrained graph from map above
- [ ] **F2** — Verify solver paths match BFS paths
- [ ] **F3** — Resolve simultaneous conflict at `3,1` / `3,0` (stagger or CBS + `departure_blockers`)

---

## G. Plan execution → MQTT master (Autoxing)

- [ ] **G1** — Replace `SharedMemoryAgentController` with VDA5050 MQTT controller for real robots
- [ ] **G2** — On plan dispatch: build order JSON and publish to `uagv/v2/Manufacturer/S001/order`
- [ ] **G3** — Subscribe `.../state`; on progress / `lastNodeSequenceId`, publish `orderUpdateId++` with next horizon `released: true`
- [ ] **G4** — Run `example_autoxing_client.py` against compose MQTT (`CONFIG["broker"]` → `mqtt-broker:1883` in Docker)
- [ ] **G5** — Fix example gaps: `NodePosition` without theta, hardcoded `map_id` (TODO in `example_autoxing_client.py` L37–38)

---

## H. Reeman (clone Autoxing pattern)

- [ ] **H1** — `example_reeman_client.py` — adapter + robot-specific bridge (or simulator)
- [ ] **H2** — `publish_reeman_route.py` — MQTT publisher to `uagv/v2/{mfg}/{sn}/order`
- [ ] **H3** — Distinct `client_id`, `serial_number`, broker host in CONFIG
- [ ] **H4** — Grid coordinates for path `5,2 → 5,1 → 4,1 → 3,1 → 3,0 → 4,0`

---

## I. End-to-end demo & verification

- [ ] **I1** — Document run sequence:
  1. `docker compose up`
  2. onboard both robots
  3. send scheduler batch or `send_mapf_schedule.py`
  4. (optional) manual MQTT fallback per robot
- [ ] **I2** — Verification script: subscribe both `.../state` topics; assert goals reached
- [ ] **I3** — Update `payload.drawio` legend: Master = MQTT publisher scripts, not C++ REST
- [ ] **I4** — Smoke test without real robots: MQTT mock state + fake `node_reached` loop

---

## Critical path

```
A (coords) → F (graph) → E (AMQP↔ROS) → D (schedule) → B+G (MAPF→MQTT, Autoxing) → H (Reeman) → I (E2E)
```

### Fastest visible win

Skip scheduler/orchestrator temporarily: run MAPF locally (ROS), convert plan to order JSON manually, run publisher + `example_autoxing_client.py`.

### Full stack win

C1–C5 + E1–E3 + D1–D2 + B3 + G1–G3 + H1–H2.

---

## Gaps in the example master (today)

| Gap | Where | Related todo |
|-----|-------|----------------|
| All nodes `released: true` | `publish_autoxing_l300_route.py` | G3 |
| Fixed `MAP_ID = "gametl_demo"` | publisher | A1 |
| Grid nodes `0,1` not used | publisher uses `(-11, 1.2)` etc. | A1 |
| No `orderUpdateId++` stitching | publisher sends once | G3 |
| Single robot only | one topic `S001` | H3 |
| No link from plan executor | PyBullet shared memory | G1 |

---

## Stack readiness summary

| Hop | Status |
|-----|--------|
| Dashboard → Scheduler | Gap: no process executor |
| Scheduler → AMQP Schedule | Gap: not wired |
| Orchestrator GoToNode | Partial: publishes `amr_mapf`, no consumer |
| AMQP → plan_server (ROS) | Missing bridge |
| CBS / graph | Partial: 7×7 open grid, not constrained |
| plan_executor | Missing from compose; PyBullet only |
| Executor → MQTT orders | Missing (use publisher pattern) |
| Autoxing adapter | Manual; off-compose |
| Reeman | Missing entirely |

Shipped demo (`fixtures/send_schedule.py`) is MANIP1/SNS1 MQTT workflow — different scenario.
