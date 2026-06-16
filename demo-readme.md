# Two-robot MAPF / VDA5050 demo

## Dry run (no robots)

```bash
docker compose --profile dry-run up --build   # dry-run is also the default (.env)
```

Trigger from Swagger at http://localhost:8089/docs or:

```bash
curl -X POST 'http://localhost:8089/demo/blue-ocean?dry_run=true'
uv run fixtures/verify_orders.py   # both robots' orders on uagv/#
```

The dry-run adapters teleport their poses node by node; watch the master at
http://localhost:8000/docs (`/state`, `/map`, `/plans/mapf`).

To re-run the demo, restart the master and the adapters **together**
(`docker compose restart vda5050 autoxing-adapter reeman-adapter`) — the
master keeps per-robot order bookkeeping in memory, and adapters restarting
alone leave it stale (plans then come back `STITCH_REJECTED`).

Or soft-reset MAPF bookkeeping without restarting:

```bash
curl -X POST 'http://localhost:8089/demo/mapf-all-idle'
```

## Real physical demo

```bash
docker compose --env-file config/config.env --env-file config/config-real.env up --build
```

This swaps the dry-run services for `mapf-planner-real`,
`autoxing-adapter-real`, `reeman-adapter-real`, and `vda5050-real`. The real
demo runs on its **own topology**, separate from the dry-run grid: planner
graph `maps/gametl_demo_real.lif.yaml`, master map `gametl_demo_map.real.json`
(ARTC coordinates in the AutoXing "From Mapping 40" master frame — see
**docs/real-demo-node-coords.md** for the node table and pre-flight checklist).

Pre-flight summary:

1. Both robots localized on their maps, placed near their start nodes
   (AutoXing → `0,1`, Reeman → `6,2`).
2. `AUTOXING_BASE_URL=http://<autoxing-ip>:<port>` exported; Reeman spellbook
   robot IP configured. Reeman→AutoXing frame offset via
   `MAP_TF_STATIC_TX/TY/THETA` if the frames don't coincide (default identity).

Trigger:

```bash
curl -X POST 'http://localhost:8089/demo/blue-ocean?dry_run=false'
```

`dry_run=false` reads each robot's live pose from the master's `/state`,
snaps it to the nearest `/map` node as the start, and plans to the configured
goals (autoxing → `3,0`, reeman → `2,0`; see `blue_ocean_robots.json` in
`rts_demo_server`). Errors: 502 = master unreachable, 409 = robot has no
pose / pose too far from any node (`SNAP_MAX_DIST_M`).

## Pipeline

```
POST /demo/blue-ocean ──AMQP Schedule──▶ task-orchestrator (GoToNode)
  ──amr_mapf TaskRequest──▶ mapf-planner (CBS on maps/gametl_demo.lif.yaml)
  ──POST /plans/mapf──▶ vda5050 master ──VDA5050 order (MQTT)──▶ adapters
```

The master re-resolves order coordinates by node name against its loaded
map (`MASTER_MAP_FILE`), so the planner always works in grid frame and the
map file is the single source of dispatched coordinates.
