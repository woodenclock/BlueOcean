# VDA5050 jack action — architecture

> ARES PRIVATE — internal design notes.

How `jackUp` / `jackDown` flows through the Blue Ocean stack end to end.

---

## Overview

```
POST /demo/navigate-to
  { goal_node, goal_actions: [{action_type: "jackUp"}] }
        │
        ▼
  Scheduler (demo_routes/blue_ocean.py)
  builds GoToNode schedule → AMQP @RECEIVE@
        │
        ▼
  Task orchestrator → amr_mapf TaskRequest
  (goal_actions in taskParams[0])
        │
        ▼
  MAPF planner (blue_ocean_planner_service.py)
  stores goal_actions per robot_id
  POST /plans/mapf { waypoints: [..., { name:"3,0", actions:[{action_type:"jackUp"}] }] }
        │
        ▼
  VDA5050 master webserver (example_master_webserver.py)
  build_plan_order → Node.actions = [vda.Action(action_type="jackUp", blocking_type=HARD)]
  master.assign_order → publish Order over MQTT
        │
        ▼
  Adapter client (example_autoxing/reeman_adapter_client.py)
  on_navigate(node) called by C++ spin thread
    1. drive to node (navigate REST → poll)
    2. _execute_node_actions(node, nav)
       for each action in node.actions:
         set_action_states([RUNNING])
         call jack_up() / jack_down() spellbook → robot REST API
         set_action_states([FINISHED | FAILED])
    3. node_reached(node)
        │
        ▼
  Robot (AutoXing: POST /services/jack_up
         Reeman:   POST /cmd/hydraulic_up)
```

---

## Key VDA5050 concepts used

| Concept | Role here |
|---|---|
| **Node actions** (`Order.node.actions`) | Carry `jackUp`/`jackDown` attached to the goal node. Custom `actionType` — the spec permits any string beyond the 9 predefined ones. |
| **`blockingType: HARD`** | Robot must not advance to the next node until the action is FINISHED. Enforced by calling `node_reached` only after the jack completes. |
| **`actionStates`** in State | Adapter calls `NavigationManager.set_action_states(...)` as RUNNING → FINISHED. The master reads these from `State.action_states` and includes them in `/ws/state`. |
| **Instant actions** (`InstantActions`) | Bound on the master side (`assign_instant_actions`); used by `POST /actions/instant/{robot_id}` for dashboard send. Adapter-side C++ subscription not yet wired — node actions are the production path. |

---

## State flow to dashboard

```
adapter set_action_states([RUNNING])
    → VDA5050 MQTT state publish (1 Hz)
    → master AGV.get_last_state().action_states
    → _jack_state_from_action_states()  →  "jacking_up" / "up" / "down"
    → /ws/state  { jack_state, action_states: [...] }
    → dashboard AgvStateTable  →  "Raising…" / "Lifted" / "Down" badge
```

Direct-REST jack calls (`POST /actions/jack/{id}/up|down`) update the
`_jack_states` cache as a fallback when VDA5050 `action_states` are empty
(e.g. Reeman's jack has no state endpoint).

---

## Files changed

| File | What changed |
|---|---|
| `master_bindings.cpp` | `InstantActions`, `InstantActionDecision`, `InstantActionAssignmentResult`, `assign_instant_actions` bound |
| `vda5050_core_py/__init__.py` | New exports |
| `example_autoxing_adapter_client.py` | `_execute_node_actions` + jack spellbook import |
| `example_reeman_adapter_client.py` | Same |
| `example_master_webserver.py` | `PlanWaypoint.actions`, node action build in `build_plan_order`, `/actions/instant/{id}`, `action_states` in state snapshot |
| `blue_ocean_planner_service.py` | `task_goal_actions` dict, `goal_actions` → last waypoint |
| `demo_routes/blue_ocean.py` | `NavigateToRequest.goal_actions`, threaded into schedule config |
| `types.ts` | `AgvActionState`, `action_states` on `AgvState` |
| `master-api.ts` | `postInstantActions` |

> **Rebuild required** after changing `master_bindings.cpp`:
> `colcon build --packages-select vda5050_core_py`
