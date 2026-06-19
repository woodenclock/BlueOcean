# 2026-06-19 — Fix: AMQP heartbeat timeout wedges task orchestrator

## Symptom

During MAPF navigation (Reeman rack mission, autoxing GoToNode, etc.):

- RabbitMQ logs: `missed heartbeats from client, timeout: 60s`
- Task orchestrator logs: `Published task urn:ngsi-ld:Task:…, awaiting response` (never unblocks)
- Scheduler mission runner may sit in `navigating` if the robot never receives a plan

## Cause

The MAPF planner (`blue_ocean_planner_service.py`) used `pika.BlockingConnection` and ran CBS + HTTP (`POST /plans/mapf`) on the **same thread** that services AMQP heartbeats. Work lasting longer than RabbitMQ’s 60s heartbeat window caused the broker to drop the planner connection before `TaskStatus` could be published.

A hung CBS solve (`Solving with CBS..` with no `Solved.`) had the same effect even when heartbeats were the immediate trigger.

## Fix (in code)

1. **Planner worker thread** — `solve_batch` spawns a daemon thread for CBS + HTTP; the pika I/O thread keeps consuming heartbeats and inbound messages. `TaskStatus` is published via a short-lived AMQP connection (same pattern as the master’s `TaskComplete` publisher).
2. **CBS wall-clock timeout** — `PLANNER_CBS_TIMEOUT_S` (default 30) caps `coordinator.solve`; on timeout the planner publishes `TaskStatus ERROR` and **recreates the CBS executor** so a hung solve cannot wedge later requests.
3. **Orchestrator timeout** — `GOTO_AMQP_TIMEOUT_S` (default 120) caps GoToNode’s wait for `TaskStatus`; on timeout the workflow fails instead of hanging forever.
4. **Demo reset (UI + scheduler)** — VDA Visualiser **Stop & reset** (per robot, always clickable) and **Reset demo** (all robots) call scheduler endpoints that stop motion, clear missions, reset master MAPF plans, and publish `MapfReset` (which aborts any in-flight CBS worker).

## Environment variables

| Variable | Default | Service | Purpose |
|---|---|---|---|
| `PLANNER_CBS_TIMEOUT_S` | `30` | mapf-planner-real | Max seconds for one CBS solve |
| `GOTO_AMQP_TIMEOUT_S` | `120` | task-orchestrator | Max seconds GoToNode waits for TaskStatus |
| `PLANNER_BATCH_WINDOW_S` | `0.7` | mapf-planner-real | Batch window for joint CBS (unchanged) |

## Recovery (if already wedged)

**During a live demo (preferred — no Docker restart):**

1. Open the [VDA Visualiser](http://localhost:3000/system/vda-visualiser).
2. **One robot stuck** — click **Stop & reset** on that robot’s card (always enabled). Clears mission + MAPF for that robot and aborts a hung CBS solve.
3. **Both robots / planner wedged / stale mission errors** — click **Reset demo** in the Robots panel header (confirm dialog). Stops all robots, clears all missions, resets MAPF on the master, and publishes global `MapfReset`.

Equivalent curl (scheduler on port 8089):

```bash
# One robot
curl -X POST http://localhost:8089/demo/cancel-navigation/reeman-1

# All robots + global MAPF reset
curl -X POST http://localhost:8089/demo/demo-reset
```

**Last resort** (planner or orchestrator process dead):

```bash
docker compose --profile real-demo restart mapf-planner-real task-orchestrator
```

Rebuild after pulling the fix:

```bash
docker compose --profile real-demo up --build mapf-planner-real scheduler
```

## Verification

After rebuild, trigger concurrent legs (e.g. autoxing navigate + Reeman rack mission). Confirm:

- Planner logs always show `TaskStatus COMPLETED` or `TaskStatus ERROR` after each `TaskRequest`
- No `missed heartbeats` from the planner container during CBS
- Orchestrator logs `GoToNode: Task … completed` or a timeout error — not an indefinite `awaiting response`
