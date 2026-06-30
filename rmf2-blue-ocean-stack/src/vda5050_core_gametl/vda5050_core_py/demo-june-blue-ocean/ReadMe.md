# Blue Ocean demo — VDA5050 adapters + spellbook bridges

# Note for Game from Game

Link: [https://autoxingtech.github.io/axbot_rest_book/reference/maps.html#get-map-detail](https://autoxingtech.github.io/axbot_rest_book/reference/maps.html#get-map-detail)

to get the map detail from the autoxing also can use `get_map_overlays` to get the map info(origin) Min will update the spellbook for the reeman to get the same.

---

Spellbook Python lives under `{bridge}/spellbook/commands/`. The bridge wrapper
adds that directory to `sys.path` and imports modules directly — **do not** run
`source spellbook/activate_autoxing.sh` or `uv sync` inside `spellbook/` for this demo.

Configure robot IP in `config/config.env` (preferred) or each bridge's
`spellbook/commands/credentials/CONSTANTS.yml` (gitignored fallback):

- Autoxing: `AUTOXING_BASE_URL=http://<ip>:8090` in config.env, or `CONSTANTS.yml`
- Reeman: `REEMAN_ROBOT_IP=<ip>` in config.env, or `CONSTANTS.yml`

## Setup

From `demo-june-blue-ocean/` (after sourcing the colcon workspace so `vda5050_core_py` is available):

```bash
uv sync
```

Optional env overrides live in repo-root `config/config.env` (symlinked as `.env`):

- `AUTOXING_SPELLBOOK_DIR` / `REEMAN_SPELLBOOK_DIR` — spellbook `commands/` dirs (relative to repo root)
- `AUTOXING_BASE_URL` — AutoXing robot REST, e.g. `http://192.168.1.50:8090` (overrides `CONSTANTS.yml` when set)
- `REEMAN_ROBOT_IP` — Reeman robot host, e.g. `192.168.1.51` (overrides `CONSTANTS.yml` when set)

Spellbook and adapters use env when set, otherwise the active robot in each bridge's
`spellbook/commands/credentials/CONSTANTS.yml` (gitignored).

Or `source autoxing_bridge/spellbook/activate_autoxing.sh` / `activate_reeman.sh` (loads `config/config.env`).

## Run adapters

**Dry-run** (no robot; used by docker compose):

```bash
python3 example_autoxing_adapter_client.py --dry-run
python3 example_reeman_adapter_client.py --dry-run
```

**Real robot** (requires `CONSTANTS.yml` and reachable robot IP):

```bash
python3 example_autoxing_adapter_client.py
python3 example_reeman_adapter_client.py
```

**Multi-node routes:** `on_navigate` returns immediately; navigation runs on a worker thread.

## Master webserver (FastAPI + Swagger)

```bash
source ../../install/setup.bash
uv run example_master_webserver.py
# open http://127.0.0.1:8000/docs
```

## Map-frame calibration (Reeman → AutoXing)

AutoXing's map frame is the **master** frame: all VDA5050 order/state
coordinates are master-frame. At init the Reeman adapter fetches both robots'
current maps, matches **identically named waypoints** and estimates a 2D
similarity transform with [nudged](https://github.com/axelpale/nudged-py)
(lives in the umbrella repo at `maps/map_transform/`). Published `agvPosition`
is always master-frame.

Prerequisites:

- ≥3 (ideally 4+) waypoints named identically on both robots' active maps,
spread across the floor (Reeman: `/reeman/position` waypoints; AutoXing:
map overlay landmarks/chargers).
- `AUTOXING_BASE_URL` (e.g. `http://<robot-ip>:8090`) in repo-root `config/config.env`
  (overrides spellbook `CONSTANTS.yml` when set). Same file holds `REEMAN_ROBOT_IP`.

Offline rule: if AutoXing is unreachable at init, the last persisted
calibration (`MAP_TF_CACHE_PATH`, default
`~/.cache/gametl/reeman_to_autoxing_tf.json`) is reused when Reeman's map is
unchanged; otherwise the adapter starts but **blocks navigation**
(`MAP_TF_ALLOW_IDENTITY=1` forces an identity transform for demo setups).

From the umbrella repo root (deactivate repo-root `.venv` first if active —
avoids a uv `VIRTUAL_ENV` mismatch warning):

```bash
cd maps
PYTHONPATH=. uv run --project ../src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean python -m map_transform
```

The CLI auto-loads repo-root `config/config.env` for robot URLs; shell
overrides still win.

## Optional bridge test CLIs

Run from `demo-june-blue-ocean/`:

```bash
python3 -m autoxing_bridge.navigate_node 1.0 2.0 0.0
python3 -m autoxing_bridge.poll_robot
python3 -m reeman_bridge.poll_robot
python3 -m reeman_bridge.wait_for_move 1.0 2.0 0.0
```

