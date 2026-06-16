---
name: run-demo-stack
description: Run and test the two-robot MAPF/VDA5050 demo stack (brokers, task orchestrator, scheduler, mapf-planner) with docker compose. Use when starting the stack, testing the Blue Ocean demo endpoint, verifying VDA5050 orders, or debugging the AMQP/MQTT pipeline.
---

# Run the demo stack

## Compose rules (important)

- **For testing, run `docker compose` in the foreground — do NOT use `-d`.**
  Launch it as a background *process* (so you can keep working) but without
  the `-d` flag, watch the streamed logs, and **kill it / bring the stack
  down when testing is done** (`Ctrl-C` or `docker compose ... down`).
  `-d` is only for when the user explicitly wants the stack left running.
- Always include the overlay file; the planner lives there:
  `docker compose -f docker-compose.yml -f docker-compose.mapf-demo.yml ...`

## Start the stack (foreground)

```bash
docker compose -f docker-compose.yml -f docker-compose.mapf-demo.yml up --build \
  amqp-broker mqtt-broker task-orchestrator mapf-planner
```

The scheduler usually runs from its own compose (`cd src/rmf2_scheduler_gametl
&& docker compose up`, port 8089, container `rmf2_scheduler`); it joins the
umbrella network `${COMPOSE_PROJECT_NAME}_rmf2-net` (e.g. `rmf2_demo_gametl-dry-run_rmf2-net`), which must already exist
(start the umbrella brokers first). The umbrella compose also defines the same
scheduler container — only one of the two can run at a time.

## Trigger + verify

```bash
# fire the demo (or press it in Swagger at http://localhost:8089/docs)
curl -X POST 'http://localhost:8089/demo/blue-ocean'

# assert both VDA5050 orders arrive with the expected node sequences
uv run fixtures/verify_orders.py   # deps declared in-script (PEP 723)
```

Healthy run: mapf-planner logs each TaskRequest, a CBS plan per robot as DEBUG
JSON (autoxing waits at 2,1 with departure_blockers; reeman goes first), one
VDA5050 order per robot on `uagv/v2/{Manufacturer/S001,Reeman/R001}/order`,
and TaskStatus COMPLETED; task-orchestrator logs both workflows completed.

## When done

Kill the foreground compose process, then:

```bash
docker compose -f docker-compose.yml -f docker-compose.mapf-demo.yml down --remove-orphans
```

Leave the user's standalone scheduler container alone unless asked.

## Gotchas

- Python is pinned to 3.12 (numpy 1.26.4 has no 3.13 wheels).
- mapf-planner code changes need an image rebuild (`--build`); same for the
  scheduler (`rts_demo_server` is baked into the image, not bind-mounted).
- RabbitMQ mgmt UI: http://localhost:15672 (guest/guest); MQTT spy:
  `docker run --rm --network rmf2_demo_gametl-dry-run_rmf2-net eclipse-mosquitto:2 mosquitto_sub -h mqtt-broker -t 'uagv/#' -v`
