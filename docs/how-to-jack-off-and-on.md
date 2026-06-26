# How to jack off and on

How the fork/jack (load lift) is raised and lowered across the Blue Ocean stack
— manually, over the master REST API, and automatically at rack nodes during a
multi-goal mission.

> **Scope note:** jack control is **AutoXing only** in this demo. Reeman has no
> manual jack UI, no mission rack jack, and `POST /actions/jack/reeman-*` returns
> 501. AutoXing rack pick/drop uses the card's **Pick rack** row or `POST /demo/pick-rack`.

---

## The three ways to move the jack

| Way | Trigger | Path | Decides direction |
| --- | --- | --- | --- |
| **Manual button** | RMF UI → **Direct Control** card → *Jack up* / *Jack down* (AutoXing only) | UI → master `POST /actions/jack/{robot_id}/{direction}` → robot REST | You |
| **REST (direct)** | `curl` the master endpoint (AutoXing only) | master `/actions/jack/...` → robot REST | You |
| **Rack pick/drop (UI)** | AutoXing robot card **Pick rack** row | scheduler → spellbook `pick_rack` (align_with_rack, jack, to_unload_point) | You (pickup + putdown rack) |
| **Rack pick/drop (legacy)** | `POST /demo/rack-direct` | scheduler → direct navigate to map node + master `/actions/jack/...` | You (explicit up/down per leg) |

All three end at the same master endpoint, so they behave identically on the
robot. Only *who decides the direction* differs.

---

## Jack state semantics

The master reports each robot's jack state on `GET /state` (`agvs[].jack_state`):

| `jack_state` | Meaning | UI badge |
| --- | --- | --- |
| `up` / `hold` | Fork raised — **carrying a load** | Lifted (green) |
| `down` | Fork lowered — **empty** | Down (gray) |
| `jacking_up` / `jacking_down` | In transition | Raising… / Lowering… (yellow) |
| `unknown` / `null` | Not reported yet | Unknown / — |

State source (`example_master_webserver.py:_agv_state_snapshot`): VDA5050 order
action-states are authoritative when present; otherwise it falls back to the
`_jack_states` cache that the direct `/actions/jack` endpoint updates. Because
the mission runner uses the direct endpoint (not order actions), the cache is
what the next leg reads — so the auto-toggle sees the result of the previous
jack.

---

## Per-robot REST (what the master calls)

Set per robot by `endpoint` in `maps/<VDA5050_MAP_ID>/robots.yaml`.

- **AutoXing** — `POST {endpoint}/services/jack_up` / `/services/jack_down`,
  monitored via WS `/jack_state`. State set to `jacking_up` / `jacking_down`.
- **Reeman** — jack is disabled in this demo (`501` from `/actions/jack`).
- **No endpoint configured (dry-run, AutoXing)** — no REST call; the master flips
  in-memory `_jack_states` so the UI/badge still react.

(See `example_master_webserver.py:jack_control`.)

---

## 1) Manual — RMF UI

1. Open the **VDA5050 visualiser** page.
2. Scroll to **Direct Control** (bottom).
3. On the **AutoXing** card, click **Jack up** or **Jack down**.

The button calls `postJack(robotId, dir)` →
`POST {MASTER_BASE}/actions/jack/{robot_id}/{direction}`
(`master-api.ts`). The jack badge on the robot status card reflects the result.

## 2) Manual — REST

```bash
# raise the fork on autoxing-1
curl -X POST http://localhost:8000/actions/jack/autoxing-1/up

# lower it
curl -X POST http://localhost:8000/actions/jack/autoxing-1/down
```

`direction` must be `up` or `down`. `robot_id` is the unified id
(`reeman-1`, `reeman-2-blue`, `autoxing-1`).

## 3) Rack pick/drop (AutoXing)

Use the **Pick rack** row on the AutoXing robot card (pickup **West** / putdown
**FarNorth**, then **Pick rack**) or `POST /demo/pick-rack`. This runs the
spellbook sequence: rack size detection → `align_with_rack` → jack up →
`to_unload_point` → jack down at hardcoded onboard-map poses (no MAPF, no layout
nodes). The jack badge on the card updates live via the master WebSocket.

```bash
curl -X POST http://localhost:8089/demo/pick-rack \
  -H 'Content-Type: application/json' \
  -d '{"robot_id":"autoxing-1","pickup":"Rack_West","putdown":"Rack_FarNorth"}'

curl http://localhost:8089/demo/mission/autoxing-1
```

List hardcoded rack poses:

```bash
curl http://localhost:8089/demo/pick-rack/points
```

**Legacy** — navigate to layout rack *nodes* then jack (`POST /demo/rack-direct`):

```bash
curl -X POST http://localhost:8089/demo/rack-direct \
  -H 'Content-Type: application/json' \
  -d '{"robot_id":"autoxing-1","legs":[{"node":"1,5","jack":"up"},{"node":"3,10","jack":"down"}]}'
```

Reeman missions (`POST /demo/navigate-mission`) reach rack nodes but **skip**
jack.

---

## Rack nodes

Racks are where the auto-toggle fires. Default (mirrors
`maps/<VDA5050_MAP_ID>/real.layout.yaml`):

| Rack | Approach (node before) | Area |
| --- | --- | --- |
| `2,4` | `2,3` | Human Zone Arm |
| `3,4` | `3,3` | Human Zone TV |

MAPF routes through the approach node automatically — it's the rack's only graph
neighbour, so a goal of `2,4` always arrives via `2,3`.

List them live:

```bash
curl http://localhost:8089/demo/racks
# {"2,4":"2,3","3,4":"3,3"}
```

Override (node ids contain commas, so use `;` between entries and `=` between
rack and approach):

```bash
RACK_NODES="2,4=2,3;3,4=3,3"   # scheduler env
```

---

## Troubleshooting

- **Jack didn't move** — check AutoXing `endpoint` in `maps/<VDA5050_MAP_ID>/robots.yaml`; test
  `POST {endpoint}/services/jack_up`.
- **Reeman rack leg did nothing** — expected; Reeman skips jack in this demo.
- **Dry-run** — with no robot endpoint, jack state only flips in master memory
  (no physical motion); good for exercising the AutoXing rack/UI flow.

## Related

- `docs/real-demo-node-coords.md` — node coordinates / map frame
- `maps/<VDA5050_MAP_ID>/real.layout.yaml` — `racks:` block (canonical rack list)
- `autoxing_bridge/spellbook/pick_rack.py` — canonical spellbook (robot REST sequence)
- `demo_routes/pick_rack.py` — thin scheduler wrapper (`POST /demo/pick-rack`)
- `demo_routes/mission.py` — mission runner; legacy rack-direct + MAPF `goal_jacks`
- `example_master_webserver.py` — `/actions/jack`, `/state`, jack state
