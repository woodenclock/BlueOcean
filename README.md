# Project Blue Ocean — RMF2 demo stack

> **ARES PRIVATE** — internal demo data (robot IPs, map ids, ARTC site
> coordinates are sensitive). Do not paste live credentials or addresses here;
> treat the linked `docs/` pages as confidential.

A two-robot Multi-Agent Path Finding (MAPF) + VDA5050 coordination demo. A
single dispatch schedules two heterogeneous robots (**AutoXing**, **Reeman**) to
their goals; a Conflict-Based Search (CBS) planner resolves their path conflict
and dispatches collision-free VDA5050 orders. The whole system is one
`git clone` + `docker compose up` against physical robots.

AutoXing and Reeman robots on the demo floor

📹 [MS Teams Video of the Demo](https://itssastar.sharepoint.com/:v:/r/sites/RMF2-Dev-Team/Shared%20Documents/%5BDev%5D%20VDA5050/BlueOceanDemoVideo-GameTL%201-2026-06-15-8000.mp4?csf=1&web=1&e=ukqdqB)

## Stack

All five source repos are checked out on the `demo-june-blue-ocean` branch
(pinned by `.repos`; see [Branch](#branch-demo-june-blue-ocean)).


| Service                   | Repo                            | Port variable                  |
| ------------------------- | ------------------------------- | ------------------------------ |
| UI dashboard              | `rmf2-ui-gametl`                | `UI_PORT`                      |
| Scheduler API             | `rmf2_scheduler_gametl`         | `SCHEDULER_PORT`               |
| Task orchestrator         | `rmf2_task_orchestrator_gametl` | `TASK_ORCHESTRATOR_PORT`       |
| MAPF planner (CBS)        | `res_mapf_gametl`               | —                              |
| VDA5050 master + adapters | `vda5050_core_gametl`           | `VDA5050_PORT`                 |
| MQTT broker               | `eclipse-mosquitto`             | `MQTT_PORT`                    |
| AMQP broker               | `rabbitmq`                      | `AMQP_PORT` / `AMQP_MGMT_PORT` |




## Prerequisites

- Docker + Docker Compose v2
- [vcstool](https://github.com/dirk-thomas/vcstool): `pip install vcstool`
- [uv](https://docs.astral.sh/uv/) — only for running the fixtures and the map
calibrator (both provision their own deps; no `pip install` needed)

---



## Quick Start

```bash
# 1. Clone, then check out the demo branch
git clone git@gitlab.com:ROSI-AP/rmf2/blueocean/rmf2-blue-ocean-stack.git
cd rmf2-blue-ocean-stack && git checkout demo-june-blue-ocean

# 2. Pull all five source repos into src/ (each on demo-june-blue-ocean)
vcs import src < .repos

# 3. If need to map_transform 
cd maps && uv run get_map_n_transform.py AMAV-X # or DIR of maps to be tranformed 

# 4. Build and start the stack (first build ~2 min for the ROS images)
docker compose up --build
```

Services come up in dependency order. Copy `.env.sample` to `.env` first; the
active map floor is set there via `VDA5050_MAP_ID` (`AMAV-X` | `l1-artc`).

## Run the demo (physical robots)

The two-robot conflict scenario: the CBS planner sends both robots through the
shared corridor one at a time — one crosses while the other holds at the
intersection, then follows.

The stack plans on the selected floor's topology
(`maps/${VDA5050_MAP_ID}/real.layout.lif.json`), with coordinates in that floor's
AutoXing master frame (`AMAV-X` or `l1-artc` — `VDA5050_MAP_ID` is both the
master map id and the floor dir name). Robot **goals** are read from
`maps/robots.yaml` (`routes.real`); **starts** are not configured — each robot's
live `/state` pose is snapped to the nearest map node (within `SNAP_MAX_DIST_M`,
default 3 m).

**Pre-flight**

1. Both robots powered and localized on their onboard maps (within
  `SNAP_MAX_DIST_M` of a map node).
2. Each robot's REST `endpoint` set in `maps/robots.yaml`.

```bash
docker compose up --build

# Verify both robots received the expected VDA5050 orders on MQTT
uv run fixtures/run_verify_orders.py
```

Trigger the moves from the scheduler's Swagger page —
[localhost:8089/docs](http://localhost:8089/docs) → `POST /demo/navigate-to` →
**Try it out** → pick the `autoxing` / `reeman` example → **Execute** — or from
the dashboard's **VDA Visualiser** (click a node, **Apply**). The scheduler reads
each robot's live pose from the master `/state`, snaps it to the nearest `/map`
node as the start, and plans to the goals in `maps/robots.yaml`.

**Re-running.** Restart the master and its adapters *together* — the master
holds per-robot order state in memory, so adapters restarting alone leave it
stale (orders come back `STITCH_REJECTED`):

```bash
docker compose restart vda5050 autoxing-1 reeman-2-blue
```

Alternatively `POST /demo/mapf-all-idle` clears stored plans/dispatch records on
the master without a restart.

Full node table and pre-flight checklist: [docs/real-demo-node-coords.md](docs/real-demo-node-coords.md).

## Dashboard & VDA Visualiser

The UI is at [localhost:3000](http://localhost:3000) (**Home → System → VDA
Visualiser**). It draws the live master map + robot poses over
`ws://localhost:8000/ws/state`, and exposes manual **Jack up / down**, the rack
**Pick up / Drop off** flow, and a **Direct Control** panel (bypasses MAPF —
sends master-frame x/y straight to the robot).

RMF2 dashboard — Home

*Dashboard home — Manual Wiki, Network, Simulation, Map, VDA Visualiser, Schedule.*

VDA Visualiser — live map and robot poses

*Live map and robot poses (*`autoxing-1`*,* `reeman-1`*) over the master WebSocket.*

VDA Visualiser — rack pick / drop

*Per-robot rack **Pick up / Drop off** rows (the AutoXing rack flow).*

The visualiser draws the map the VDA5050 master serves at `GET /map` (metric
nodes) and `GET /map/grid` (planner grid view). Nodes are **not** configured in
the UI — to change a coordinate, edit the layout file (below) and restart the
master.

---



# Steps to make a new demo

1. Map the "new" space with for each robot. make a new m

```bash
# 3. (Real demo only) drop each robot's onboard map under maps/, then calibrate.
#    See "Map & topology" below and docs/how-to-add-transform-new-map.md.
cd maps
PYTHONPATH=. uv run --no-project \
  --with opencv-python-headless --with numpy --with nudged --with pyyaml --with requests \
  python -m map_transform.image_calibrate \
  --master-map-dir autoxing-1_map \
  --robot-map-dir reeman-2-blue_map
cd ..
```



## Map & topology

There is one layout file per floor — the **single source of truth**, loaded by
the VDA5050 master (`MASTER_MAP_FILE` → `maps/${VDA5050_MAP_ID}/real.layout.lif.json`)
and served over `/map` + `/map/grid`. The floor is chosen by `VDA5050_MAP_ID`
(see [maps/README.md](maps/README.md)).

Node ids are `"col,row"` grid strings — the planner derives its integer CBS grid
straight from the id (no separate grid field); `x`/`y` are the metric
master-frame coordinates the master dispatches against. Robot start/goal live in
`maps/${VDA5050_MAP_ID}/robots.yaml`, not in the layout.

- **Add / move a node:** [docs/how-to-add-node-to-map.md](docs/how-to-add-node-to-map.md)
(every edge must step ±1 in one axis — skipping grid ids breaks CBS).
- **Real-demo node coordinates:** [docs/real-demo-node-coords.md](docs/real-demo-node-coords.md)
- **Re-map a robot / recompute its frame transform:** [docs/how-to-add-transform-new-map.md](docs/how-to-add-transform-new-map.md)

`maps/` is mounted into the master, so coordinate edits need only a restart
(`docker compose up -d vda5050`), no rebuild.

### Frame transforms

Each robot localizes on its own native map; `maps/map_transforms.yaml` declares
the shared `master_frame` plus a per-robot `robot_to_master` similarity (AutoXing
is identity; Reeman is a ~177° + (1.33, 1.99) m offset). The master loads this
file and serves it at `GET /transform`; **each adapter fetches its transform from
the master** at startup — robots only need `ROBOT_ID` + `MASTER_URL`.

## Robots & jack control


| Robot              | Frame                                       | Jack                                                                 | Reference                            |
| ------------------ | ------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------ |
| **AutoXing**       | master (frame = `VDA5050_MAP_ID`), identity | `/services/jack_up` · `_down`; rack pick/drop via the tablet         | [docs/autoxing.md](docs/autoxing.md) |
| **Reeman** FlyBoat | own frame, calibrated to master             | hydraulic lift (`/cmd/hydraulic_up`/`_down`); no jack-state endpoint | [docs/reeman.md](docs/reeman.md)     |


Jack control is **AutoXing-only** in this demo (Reeman `POST /actions/jack`
returns `501`). Manual jack, master-REST jack, and rack pick/drop are all
covered in [docs/how-to-jack-off-and-on.md](docs/how-to-jack-off-and-on.md).

## Service ports

All ports live in `[.env](.env.sample)` (auto-loaded by Compose; copy from
`[.env.sample](.env.sample)`). Fixtures read the same variables when
`--port`/`--host` is omitted.


| Service             | URL / port (default)                                                                                 |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| UI dashboard        | [http://localhost:3000](http://localhost:3000)                                                       |
| Scheduler API docs  | [http://localhost:8089/docs](http://localhost:8089/docs)                                             |
| Task orchestrator   | [http://localhost:2727](http://localhost:2727)                                                       |
| VDA5050 master docs | [http://localhost:8000/docs](http://localhost:8000/docs) (`/state`, `/map`, `/transform`, `/robots`) |
| MQTT broker         | 1883                                                                                                 |
| RabbitMQ management | [http://localhost:15672](http://localhost:15672) (guest / guest)                                     |




## Demo fixtures

Each fixture declares its own deps (PEP 723), so `uv run` provisions them — no
`pip install`. Use `--host` / `--broker` to target a remote VM.

```bash
uv run fixtures/run_verify_orders.py          # subscribe to VDA5050 orders, assert node sequences
uv run fixtures/run_send_schedule.py          # publish a Schedule to the orchestrator via AMQP
uv run fixtures/run_send_mapf_task_request.py # publish an amr_mapf TaskRequest directly to AMQP
uv run fixtures/run_publish_mqtt_route.py     # publish a raw VDA5050 route order via MQTT
```

See `fixtures/demo_tasks.json` for sample payloads.

## Repo layout

```
rmf2-blue-ocean-stack/
├── .repos                       # vcstool manifest (5 repos, demo-june-blue-ocean)
├── .env.sample                  # stack config template (ports, VDA5050_MAP_ID) — copy to .env
├── docker-compose.yml           # full stack (real physical robots)
├── docker/                      # task-orchestrator / res-mapf / vda5050 Dockerfiles
├── config/                      # mosquitto.conf, task_orchestrator.toml
├── maps/                        # per-floor dirs (l1/, l3-amav-x/) + shared map_transform/ tooling
├── fixtures/                    # uv-run demo publishers + order verifier
├── docs/                        # architecture + how-to references (linked above)
└── src/                         # populated by: vcs import src < .repos
```

---



## Branch: `demo-june-blue-ocean`

The demo depends on a coordinated set of changes across all five source repos.
`vcs import` reads `.repos` and checks out `demo-june-blue-ocean` automatically;
if you clone a repo manually, check out that branch before building.