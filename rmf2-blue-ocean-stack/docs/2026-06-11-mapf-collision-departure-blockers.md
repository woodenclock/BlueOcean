# 2026-06-11 — Fix: robots collided in the 3,1/3,0 corridor (departure blockers never enforced)

## Symptom

In the two-robot blue-ocean demo, CBS correctly resolved the corridor
conflict (autoxing must wait at `2,1` behind reeman), but both robots drove
through `3,1`/`3,0` at the same time anyway. The vda5050 log also showed

```
[AGV] Stitch validation rejected order mapf_reeman_v2_* (update 0) ... 1 error(s)
```

while the planner reported `accepted=True dispatched=True` for the same
order.

## Root cause (three stacked gaps)

1. **Per-request replanning raced.** The scheduler fires two independent
   schedules; the planner (`blue_ocean_planner_service.py`) replanned on
   *each* TaskRequest. The first robot's solo v1 plan (no blockers — there
   was nothing to conflict with yet) dispatched immediately and the robot
   drove off. ~50 ms later the joint v2 plans (with `departure_blockers`)
   arrived, but the in-flight v1 order could not be replaced: a **new
   order_id while an order is in flight is rejected by the order stitcher**
   (`order_stitcher.cpp:117-127` — concurrent orders need cancelOrder,
   which is unimplemented adapter-side, `adapter.cpp` `on_cancel` is
   reserved/commented). The misleading `dispatched=True` happens because
   `assign_order`'s pre-flight passes synchronously and the stitch rejection
   fires later on the AGV publish-queue thread.
2. **The master dropped the blockers.** `build_plan_order` in
   `example_master_webserver.py` marked every node/edge `released=True` and
   only *stored* `departure_blockers` — its docstring said enforcement was
   pending order stitching.
3. **The adapter ignored `released` anyway.** `NavigationStrategy::step()`
   (`vda5050_core/src/adapter/adapter.cpp`) iterated all order nodes without
   checking `released`, so even a correct base/horizon split would not have
   stopped the robot.

## Fix

One change per layer:

- **Planner — batch + progress**
  (`src/res_mapf_gametl/res_mapf/examples/blue_ocean_planner_service.py`):
  TaskRequests arriving within `PLANNER_BATCH_WINDOW_S` (default 0.7 s) are
  collected and solved in **one joint CBS pass** (`solve_batch` via pika
  `call_later`), so the solo-plan race never happens. Each waypoint in the
  `/plans/mapf` payload now carries its CBS `progress` timestep — the value
  other robots' `required_progress` compares against (wait-step duplicates
  keep the later timestep).

- **Master — base/horizon dispatch + release watcher**
  (`example_master_webserver.py`):
  - `build_plan_order(..., released_until, from_idx)`: nodes/edges are
    released only up to and including the **first waypoint with departure
    blockers**; everything after is the unreleased horizon (§6.4).
  - A `_release_watcher` asyncio task (300 ms) checks each held order's hold
    waypoint: when every blocker's robot has progress ≥ `required_progress`
    (progress = the `progress` of the plan waypoint matching that robot's
    `last_node_id`), it publishes a **stitched order update** — same
    order_id, `order_update_id + 1`, starting at the hold node (§6.6.2) —
    releasing through the next hold (or the end). `publish_order` is used
    (skips readiness pre-flight; the stitch guard still queues the update
    until the AGV reaches the stitch point, then the lifecycle drains it).
  - Replans for a mid-order robot reuse the active order_id with a bumped
    update id (`_resolve_order_identity`) instead of a new order_id, so they
    queue instead of being stitch-rejected. `state.dispatched_orders` tracks
    `{order_id, update_id, released_until}` per robot (updates that land as
    `STITCH_QUEUED` also claim their update id).

- **Adapter — honor the horizon**
  (`vda5050_core/src/adapter/adapter.cpp`, `NavigationStrategy::step`):
  never dispatch an unreleased node — the AGV holds until an OrderUpdate
  replaces `nodes_` and iteration restarts from its first (released) node.
  Requires the vda5050 image rebuild (C++ in-image colcon build).

## Verified behaviour (two consecutive clean runs)

```
plan v1 autoxing: 0,1 → 1,1 → 2,1 → 3,1 → 3,0   (2,1 waits reeman@4.0, 3,1 waits reeman@5.0)
plan v1 reeman:   5,2 → 5,1 → 4,1 → 3,1 → 3,0 → 4,0

autoxing reaches 2,1 and HOLDS (horizon)
reeman passes 3,1, reaches 3,0          → "Blockers at 2,1 cleared" (update 1)
autoxing proceeds to 3,1
reeman reaches 4,0, order completes     → "Blockers at 3,1 cleared" (update 2)
autoxing proceeds to 3,0, order completes
```

The corridor is never co-occupied. Repro: `docker compose up --build`, then
`curl -X POST http://localhost:8089/demo/blue-ocean`; watch the hold live on
the dashboard's VDA Visualiser page.

## Still open

- `cancelOrder` is unimplemented end-to-end (master bindings + adapter), so
  a replan that *changes* an in-flight robot's released base still cannot
  take effect; it queues and is dropped by `combine_order` if it doesn't
  start at the last released base node.
- Blocker evaluation assumes unique waypoint names per plan (revisits take
  the max matching progress).
