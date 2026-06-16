# 2026-06-11 — Feature: VDA live robot visualiser (dashboard page + WebSocket feed)

## What

A new rmf2-ui dashboard page, **System → VDA Visualiser**
(`/system/vda-visualiser`), that shows the demo map (nodes, edges, node
coordinates) and each robot's live position as a coloured arrow oriented by
its VDA5050 `theta`, plus a table with connection status, last node, and live
x / y / theta. Data streams over a WebSocket from the VDA5050 master
webserver — no polling.

## Backend (VDA5050 master webserver)

`src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean/example_master_webserver.py`:

- **`WS /ws/state`** — on connect, sends one
  `{"type": "map", "nodes": [...], "edges": [...]}` message (parsed from
  `MASTER_MAP_FILE`, cached at startup), then every ~300 ms a
  `{"type": "state", "agvs": [...]}` snapshot. Each AGV entry:
  `robot_id, manufacturer, serial_number, connection_status, last_node_id,
  x, y, theta, has_pose`. Sending the map over the WS avoids any CORS setup.
- **`GET /state`** — same snapshot as JSON, for curl debugging.
- `robot_id` is resolved from `robots.json` by manufacturer + serial; pose
  comes from `agv.get_last_state().agv_position` (x, y, theta,
  position_initialized).
- `websockets` added to both the PEP 723 block and `pyproject.toml` (the
  Docker entrypoint installs from the pyproject via `uv sync`, not the
  inline metadata).

## Frontend (rmf2-ui dashboard)

`src/rmf2-ui-gametl/apps/dashboard/`:

- New page `src/pages/dashboard/system/vda-visualiser.tsx`: plain SVG —
  edges as lines, nodes as labelled circles with their `(x, y)` printed,
  robots as triangles rotated by `-theta` (SVG y-axis is flipped; world
  y-up is handled by the coordinate mapping, not an SVG transform, so text
  stays unmirrored). Auto-reconnects every 2 s if the socket drops.
- WS URL derived from the existing `VITE_BROKER_STATUS_BASE`
  (`BrokerStatusConfig.BASE` with `http → ws`) — no new env var.
- Route added in `src/routes/index.ts`; sidebar entry in
  `src/layouts/admin-layout/admin-routes.tsx`.

## Verification

1. `docker compose up --build`
2. Open `http://localhost:3000/system/vda-visualiser` — grid renders, both
   robots at home poses, badge shows *connected*.
3. `curl -X POST http://localhost:8089/demo/blue-ocean` — both arrows move
   node-by-node to their goals, table updates live.
4. `curl http://localhost:8000/state` / `npx wscat -c
   ws://localhost:8000/ws/state` for the raw feeds.
