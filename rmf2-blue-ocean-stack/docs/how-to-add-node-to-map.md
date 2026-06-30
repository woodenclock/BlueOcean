# How to add a node to the real-demo map

> ARES PRIVATE — internal demo data (coordinates are tied to the ARTC site
> sketch; do not paste live robot IPs or addresses into this file).

This page is the quick recipe for adding a **new node** to the real-demo
topology. The whole map is one file — `maps/<VDA5050_MAP_ID>/real.layout.lif.json` — and
the planner derives its grid straight from the node ids, so there is no separate
grid to maintain. Full coordinate table lives in
[`real-demo-node-coords.md`](./real-demo-node-coords.md).

Audience: whoever extends the floor graph between runs.

## Files to change

- `maps/<VDA5050_MAP_ID>/real.layout.lif.json` — add the node under `layouts[0].nodes` and an edge under `layouts[0].edges`.
- `docs/real-demo-node-coords.md` — add the new node's row/diagram entry so the table stays the source of truth.
- `maps/<VDA5050_MAP_ID>/robots.yaml` — (only if the node is a route start/goal) point `routes.real` at it.

---

## How a node is defined

```yaml
nodes:
  "col,row": { x: <meters>, y: <meters>, deviation: 0.25 }
```

- **key `"col,row"`** — the planner grid coordinate. Must be `int,int`,
  comma-separated, **no spaces**. The MAPF planner parses this id directly into
  `(int, int)`; there is no separate `grid:` field.
- **`x` / `y`** — real-world metres in the **master frame** (AutoXing
  "l1-artc"). These are what the VDA5050 master dispatches.
- **`deviation`** — localization tolerance in metres (use `0.25` on dry-run maps;
  `1.0` matches the existing real-demo nodes).

> Reeman coordinates are **not** entered here — the adapter transforms the
> master-frame node into Reeman's frame via `maps/<VDA5050_MAP_ID>/map_transforms.yaml`.

---

## MAPF / CBS grid rules (read this first)

The CBS planner does **not** see metric `x`/`y`. It builds a 4-connected integer
grid from node ids alone. Two constraints follow:

### 1. Every new node must be connected by an edge

A node with no edge is unreachable. The master makes edges bidirectional, so
declare each hop **once**.

### 2. Adjacent nodes must differ by exactly ±1 in column **or** row

Each edge must join two ids that are **one grid step** apart — same as the
dry-run map where `0,1` connects to `1,1`, not `2,1`.

| Valid edge | Why |
|---|---|
| `0,1` ↔ `0,2` | same column, row +1 |
| `1,3` ↔ `2,3` | same row, column +1 |
| `3,1` ↔ `3,0` | same column, row −1 |

| Invalid edge | Why |
|---|---|
| `0,1` ↔ `0,3` | row skips `0,2` |
| `0,3` ↔ `2,3` | column skips `1,3` |
| `3,3` ↔ `6,3` | column skips `4,3` and `5,3` |

If you need a waypoint halfway along a long corridor, **add the intermediate
grid ids and split the edge** — do not jump ids even when `x`/`y` are correct.

**Bad** (CBS / MAPF will error or produce invalid plans):

```yaml
nodes:
  "0,3": { x: -19.7, y: -7.0, deviation: 1.0 }
  "2,3": { x: -19.7, y:  4.4, deviation: 1.0 }
edges:
  - ["0,3", "2,3"]   # ← skips 1,3
```

**Good** (fill every increment; metric coords can be midpoints):

```yaml
nodes:
  "0,3": { x: -19.7, y: -7.0,  deviation: 1.0 }
  "1,3": { x: -19.7, y: -1.3,  deviation: 1.0 }   # midpoint along the corridor
  "2,3": { x: -19.7, y:  4.4,  deviation: 1.0 }
edges:
  - ["0,3", "1,3"]
  - ["1,3", "2,3"]
```

Same pattern on the main corridor: `0,1` → `0,2` → `0,3`, and on a long
row-3 run: `3,3` → `4,3` → `5,3` → `6,3`.

Pick the **next free integer** in the direction you are extending (`"1,3"` between
`"0,3"` and `"2,3"`, `"4,3"` / `"5,3"` between `"3,3"` and `"6,3"`). The `x`/`y`
values are for robot dispatch only; CBS only sees the integer steps.

---

## Steps

### 1. Pick a grid id

Choose an unused `"col,row"` that is **exactly one step** from its neighbour(s)
on the graph — e.g. `"7,1"` past `"6,1"` on the main corridor, or `"1,3"`
between `"0,3"` and `"2,3"` on row 3. Never reuse a skipped id (no `"2,3"`
edge from `"0,3"` without `"1,3"`).

### 2. Measure its (x, y) in the master frame

Read it off the ARTC sketch / [`real-demo-node-coords.md`](./real-demo-node-coords.md),
or take it from a live AutoXing pose. Coordinates **must** be in the AutoXing
"l1-artc" frame.

### 3. Add the node  → `maps/<VDA5050_MAP_ID>/real.layout.lif.json`

```yaml
nodes:
  # ...existing...
  "7,1": { x: -4.4, y: 28.7, deviation: 0.25 }   # new node
```

### 4. Add edge(s)  ← **required**

A node with no edge is unreachable — the planner cannot route to or through it.
Each edge must connect ids that differ by ±1 in **one** axis only (see
[MAPF / CBS grid rules](#mapf--cbs-grid-rules-read-this-first)). When inserting
a midpoint, **remove** the long hop and replace it with two (or more) unit steps.

Edges are made bidirectional by the master, so declare each one **once**:

```yaml
edges:
  # ...existing...
  - ["6,1", "7,1"]
```

Inserting `1,3` between `0,3` and `2,3`:

```yaml
edges:
  # remove: - ["0,3", "2,3"]
  - ["0,3", "1,3"]
  - ["1,3", "2,3"]
```

### 5. Update the docs

Add the row + diagram entry in
[`real-demo-node-coords.md`](./real-demo-node-coords.md) so the table stays the
source of truth.

### 6. (Optional) Use it as a goal

Route endpoints live in `maps/<VDA5050_MAP_ID>/robots.yaml` (`routes.real`), **not** in the
layout file. Point a route at the new node only if it is a demo goal:

```yaml
routes:
  real: { goal: "7,1" }
```

Real demo starts come from live robot localization — do not add `start` under
`routes.real`.

### 7. Restart the master

`maps/` is mounted, so **no rebuild** is needed:

```bash
docker compose --profile real-demo up -d vda5050-real
```

### 8. Verify

```bash
# Node appears in the served map (master is on port 8000):
curl -s http://localhost:8000/map | jq '.nodes[] | select(.node_id=="7,1")'

# Drive a task to it:
uv run fixtures/run_send_mapf_task_request.py --robot-id autoxing --goal 7,1
```

---

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Node missing from `/map` | Master not restarted | `up -d vda5050-real` (step 7). |
| Planner can't route to node | No edge declared | Add an edge in step 4; restart. |
| CBS / MAPF fails or bad plan | Edge skips grid ids (e.g. `0,3`→`2,3`) | Insert every intermediate id (`1,3`, …) and split into ±1 hops. |
| Robot stops short / "too far from node" | Pose >`SNAP_MAX_DIST_M` (default 3 m) from nearest node | Space nodes ≤ a few metres apart; re-localize. |
| Reeman goes to wrong spot | Coords entered in Reeman frame | Use the AutoXing master frame; the transform handles Reeman. |
| YAML won't parse | Space in the id (`"7, 1"`) | Use `"7,1"` — no spaces. |

---

## Notes

- This only touches the **real** demo. The dry-run grid is a separate file
  (`maps/<VDA5050_MAP_ID>/dry_run.layout.yaml`) but follows the same ±1 grid rule — see
  how every dry-run edge steps one cell (`0,1`→`1,1`→`2,1`, never `0,1`→`2,1`).
- The node id encodes the grid; `x`/`y` are only for dispatch. Keep the two
  consistent so the visualiser and the planner agree.
- When densifying a corridor, interpolate `x`/`y` between endpoints for each
  new id; the grid step must still be 1 even if the physical spacing is uneven.
