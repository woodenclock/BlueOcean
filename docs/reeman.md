# Reeman FlyBoat — setup and integration reference

> ARES PRIVATE — internal demo data (robot IPs, map hashes are sensitive;
> do not paste live credentials or addresses into this file).

Quick reference for the **Reeman FlyBoat** robot in the Blue Ocean demo.
Unlike AutoXing, Reeman uses a hydraulic jack (lift table) controlled directly
via REST. Its map frame is different from the master frame and must be
calibrated. See also [`how-to-add-node-to-map.md`](./how-to-add-node-to-map.md)
and [`how-to-add-transform-new-map.md`](./how-to-add-transform-new-map.md).

---

## Stack identity

| Field | Value |
|---|---|
| `planner_id` | `reeman` |
| `fleet_id` | `reeman_1` |
| `manufacturer` | `Reeman` |
| `serial_number` | `R001` |
| Onboard map name | `1fa43762ca0bec4a673fb45d2dd544e8` (alias: `BlueOceanNeo`) |
| Robot IP env | `REEMAN_ROBOT_IP` in `config/config.env` |

All routes and onboard-map details live in `maps/robots.yaml`.

---

## Robot API (REST)

| Operation | Endpoint | Notes |
|---|---|---|
| Navigate | `POST /cmd/nav` | Body: `{x, y}` in Reeman frame; **`theta` is optional** and omitted unless the caller supplies it. Dashboard **Direct Control** and robot-card **Reset** send position-only goals; θ is a manual override in the Direct Control form only. MAPF / VDA5050 orders are also position-only (x/y). Rack docking uses an explicit bearing via `navigate_reeman_rotate_then_drive`. |
| Get pose | `GET /reeman/pose` | Returns `{x, y, theta}` in Reeman frame |
| Nav status | `GET /reeman/nav_status` | Polling during a move |
| **Jack up** | `POST /cmd/hydraulic_up` | Lifts the table; fire-and-forget |
| **Jack down** | `POST /cmd/hydraulic_down` | Lowers the table; fire-and-forget |

Jack state is **not** available via any REST or WebSocket endpoint on Reeman
FlyBoat — `reeman_bridge/spellbook/jack_state.py` returns `None` by design.
Jack status in the dashboard is derived from VDA5050 `actionStates` instead
(see [`arch.md`](./arch.md)).

Spellbook scripts live in
`src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean/reeman_bridge/spellbook/`.

---

## Frame transform

The Reeman robot lives in its own map frame. All VDA5050 coordinates are in the
**master frame** (AutoXing "From Mapping 40"). The adapter converts at dispatch
and pose-mirroring time using a 2D similarity transform from
`maps/map_transforms.yaml`.

```
VDA5050 order (master frame) → to_robot(x, y) → POST /cmd/nav (Reeman frame)
GET /reeman/pose (Reeman frame)  → to_master(x, y) → VDA5050 agvPosition
```

To recompute after a re-map → [`how-to-add-transform-new-map.md`](./how-to-add-transform-new-map.md).

---

## Jack operations — VDA5050 integration

From the demo stack's perspective, jack up/down at the goal node is a
**VDA5050 node action**. Pass `goal_actions` in `POST /demo/navigate-to`:

```json
{
  "robot_id": "reeman",
  "goal_node": "2,0",
  "goal_actions": [{ "action_type": "jackUp" }]
}
```

The action flows: scheduler → MAPF planner → `/plans/mapf` waypoint actions →
VDA5050 `Order.node.actions` → adapter `on_navigate` → `hydraulic_up/down` REST
→ `set_action_states` (RUNNING → FINISHED). See [`arch.md`](./arch.md).

For **manual control** from the dashboard, use the **Up / Down** buttons in the
AGV table — these call `POST /actions/jack/reeman_1/up|down` which hits the
robot REST API directly (no VDA5050 involved).

---

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Robot goes to wrong position | Stale or missing transform | Recompute via `how-to-add-transform-new-map.md` and restart the adapter. |
| Jack action reported FAILED | Robot busy or jack blocked | Check physical clearance; retry. |
| Jack state stuck on dashboard | REST bridge used (no VDA5050 state) | Trigger a new jack command to update. |
| Nav fails immediately | Transform not loaded | Check `MAP_TF_ADAPTER=reeman` and that `map_transforms.yaml` has a `reeman` entry. |
| "no valid Reeman→AutoXing transform" in logs | AutoXing offline at init, cache missing | Bring AutoXing online before starting the Reeman adapter; or pre-populate the cache. |

---

## Notes

- Reeman has no rack-path concept (unlike AutoXing); the jack lifts whatever
  the robot is parked under — position accuracy is critical.
- Dry-run mode teleports pose and simulates the jack action with a 1.5 s sleep.
- Reeman does not support instant actions from the VDA5050 master — use node
  actions (above) or the dashboard direct-REST buttons.
