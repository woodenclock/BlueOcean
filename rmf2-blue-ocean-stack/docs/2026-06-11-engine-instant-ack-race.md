# 2026-06-11 — Fix: lost node-ack race stalls order execution (dry-run adapters)

## Symptom

During the two-robot MAPF dry-run demo, robots stalled mid-order at a random
node and never advanced:

- reeman received `mapf_reeman_v2_*`, navigated to its first node `5,2`,
  ack'd it, then never moved to `5,1`.
- autoxing, in the same run, walked `0,1 → 1,1 → 2,1 → 3,1` and stalled
  before its final node `3,0`.

The master (`vda5050`) showed no errors for the stalled orders — the full
order was published and received. The stall was entirely AGV-side, inside the
C++ order executor of `vda5050_core`.

## Root cause

A lost-wakeup race in the execution engine's dispatch/ack handshake.

`src/vda5050_core_gametl/vda5050_core/src/adapter/adapter.cpp` (navigate
strategy) dispatches each node like this:

```cpp
engine()->emit<NodeDispatchEvent>(Priority::NORMAL, std::move(target));
engine()->step();                       // -> Python on_navigate fires here
engine()->suspend_for<NodeAckUpdate>(   // wait armed AFTER dispatch
    std::chrono::seconds(300),
    [sequence_id](auto update) { return update->sequence_id == sequence_id; });
```

`Engine::notify()` (engine.cpp) only delivered an update if a wait was
already armed (`waiting_ == true`); otherwise the update was **silently
dropped**.

The dry-run adapters call `nav.node_reached(node)` almost instantly from a
worker thread. If that ack landed in the window between `step()` (which
invokes `on_navigate`) and `suspend_for()` (which arms the wait), it was
dropped, and the executor blocked for the full 300 s timeout waiting for an
ack that had already arrived. The losing node is whichever iteration loses
the thread race — hence reeman dying on node 1 and autoxing on node 4 in the
same run.

Real robots never exposed this: physical moves take seconds, so the wait was
always armed long before the ack.

## Fix

Latch-and-consume in the engine (`vda5050_core`):

- `src/execution/engine.cpp` — `Engine::notify()` now latches the most
  recent update per type into `pending_updates_` when no wait is armed,
  instead of dropping it.
- `include/vda5050_core/execution/engine.hpp` —
  `register_internal_wait()` consumes a latched update of the awaited type
  immediately after arming the wait; if it satisfies the predicate the wait
  resolves instantly. New member
  `pending_updates_` (`type_index → shared_ptr<UpdateBase>`), guarded by the
  existing `wait_mutex_`.

A stale latched update is harmless: the wait predicate matches on
`sequence_id`, so only the ack for the awaited node can resolve the wait.

Belt-and-braces in the demo adapters
(`vda5050_core_py/demo-june-blue-ocean/example_autoxing_adapter_client.py`
and `example_reeman_adapter_client.py`): the dry-run path sleeps 0.5 s before
`node_reached`, so pretend-drives are watchable node-by-node and acks are
never effectively instantaneous.

## Also observed in the same logs (not fixed here)

```
[ERROR]: [AGV] Stitch validation rejected order mapf_autoxing_v2_* (update 0)
```

When the second TaskRequest triggers a replan, the robot still executing its
v1 order rejects the v2 order: a new `orderId` with `orderUpdateId 0` does
not satisfy VDA5050 stitching rules mid-execution. Harmless for this demo
(v1 and v2 paths are identical for autoxing), but it is the order-stitching
work tracked as todo 5.2 — the master must stitch updates onto the active
order (or defer dispatch until completion) before replans diverge.

## Verification

Rebuild required (`docker compose up --build` — C++ change triggers the full
colcon rebuild). Healthy run after the fix: `POST /demo/blue-ocean` →
both plans dispatched (`ASSIGNED`) → autoxing walks `0,1 … 3,0` and reeman
walks `5,2 → 5,1 → 4,1 → 3,1 → 3,0 → 4,0` at ~0.5 s per node, each adapter
logging `[dry-run] node_reached(...)` through to its final node.
