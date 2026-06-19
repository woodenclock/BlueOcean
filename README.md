# rmf2-demo

Umbrella repo for the GameTL RMF2 Blue Ocean demo stack. One `git clone` + `docker compose up` spins the full system.

**Important:** Every source repo must be on the `demo-june-blue-ocean` branch. The `.repos` manifest pins that branch for `vcs import`; do not substitute `main` or other branches — the demo stack is only tested and wired together on `demo-june-blue-ocean`.

## Ports

All service ports and spellbook paths live in [`config/config.env`](config/config.env). Docker Compose loads them via the `.env` symlink. Change a port in one place — host mapping and in-container listeners stay aligned.

| Variable | Service | Default |
|---|---|---|
| `UI_PORT` | UI dashboard | 3000 |
| `SCHEDULER_PORT` | Scheduler API | 8089 |
| `TASK_ORCHESTRATOR_PORT` | Task Orchestrator | 2727 |
| `VDA5050_PORT` | VDA5050 master API | 8000 |
| `MQTT_PORT` | MQTT broker | 1883 |
| `AMQP_PORT` | RabbitMQ AMQP | 5672 |
| `AMQP_MGMT_PORT` | RabbitMQ management UI | 15672 |

Fixture scripts (`fixtures/*.py`, `send_mapf_schedule.py`) read the same variables when `--port` is omitted.

## Stack

All repos below are checked out at `demo-june-blue-ocean`.

| Service | Repo | Port variable |
|---|---|---|
| UI dashboard | rmf2-ui-gametl | `UI_PORT` |
| Scheduler API | rmf2_scheduler_gametl | `SCHEDULER_PORT` |
| Task Orchestrator | rmf2_task_orchestrator_gametl | `TASK_ORCHESTRATOR_PORT` |
| MAPF planner | res_mapf_gametl | — |
| VDA5050 adapter | vda5050_core_gametl | `VDA5050_PORT` |
| MQTT broker | eclipse-mosquitto | `MQTT_PORT` |
| AMQP broker | rabbitmq | `AMQP_PORT` / `AMQP_MGMT_PORT` |

## Prerequisites

- Docker + Docker Compose v2
- [vcstool](https://github.com/dirk-thomas/vcstool): `pip install vcstool`



## Access

Default URLs (see `config/config.env` to customize):

| Service | URL |
|---|---|
| UI Dashboard | http://localhost:3000 |
| Scheduler API docs | http://localhost:8089/docs |
| Task Orchestrator diagram | http://localhost:2727 |
| VDA5050 master API docs | http://localhost:8000/docs |
| RabbitMQ management | http://localhost:15672 (guest / guest) |

## Demo Fixtures

Send a demo workflow (MANIP1 Depalletize → SNS1 Store) through the full stack:

Each fixture declares its own dependencies (PEP 723), so `uv run` provisions
them automatically — no `pip install` needed.

```bash
# Publish a Schedule to the task orchestrator via AMQP
uv run fixtures/run_send_schedule.py

# Publish a VDA5050 route order to the Autoxing L300 adapter via MQTT
uv run fixtures/run_publish_mqtt_route.py

# Use --broker / --host flags when targeting a remote host:
uv run fixtures/run_send_schedule.py --host <vm-ip>
uv run fixtures/run_publish_mqtt_route.py --broker <vm-ip>
```

See `fixtures/demo_tasks.json` for raw payload reference.

## Repo Layout

```
rmf2-demo/
├── .repos                          # vcstool manifest (all 5 repos, demo-june-blue-ocean)
├── docker-compose.yml              # full stack orchestration
├── docker/
│   ├── task-orchestrator.Dockerfile   # Rust multi-stage build
│   ├── res-mapf.Dockerfile            # ROS Jazzy + Python + MAPF
│   └── vda5050.Dockerfile             # ROS Jazzy + C++
├── config/
│   ├── mosquitto.conf              # anonymous MQTT on 1883
│   └── task_orchestrator.toml     # Docker-aware host overrides
├── fixtures/
│   ├── run_send_schedule.py            # AMQP Schedule publisher
│   ├── run_publish_mqtt_route.py       # MQTT VDA5050 route publisher
│   └── demo_tasks.json             # sample task/schedule payloads
└── src/                            # populated by: vcs import src < .repos
    ├── rmf2-ui-gametl/
    ├── rmf2_scheduler_gametl/
    ├── rmf2_task_orchestrator_gametl/
    ├── res_mapf_gametl/
    └── vda5050_core_gametl/
```

## Branch: `demo-june-blue-ocean`

This demo depends on a coordinated set of changes across all five source repos. Each repo must be on `demo-june-blue-ocean`:

| Repo | Branch |
|---|---|
| rmf2-ui-gametl | `demo-june-blue-ocean` |
| rmf2_scheduler_gametl | `demo-june-blue-ocean` |
| rmf2_task_orchestrator_gametl | `demo-june-blue-ocean` |
| res_mapf_gametl | `demo-june-blue-ocean` |
| vda5050_core_gametl | `demo-june-blue-ocean` |

`vcs import` reads `.repos` and checks out the correct branch automatically. If you clone repos manually, check out `demo-june-blue-ocean` in each one before building.
