FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app/res_mapf

COPY src/res_mapf_gametl/res_mapf /app/res_mapf
# Both demo graphs: dry-run grid + the separate real ARTC layout (MAP_FILE
# selects at runtime; the real-demo compose profile points at the real one).
COPY maps/gametl_demo.lif.yaml maps/gametl_demo_real.lif.yaml /app/maps/

# Plan-server stack only (res_mapf_planning + res_plan_execution +
# res_plan_server); skips res_pybullet so no simulator/ROS deps.
RUN uv sync --package res_plan_server --no-dev \
    && uv pip install rich pika paho-mqtt

ENV MAP_FILE=/app/maps/gametl_demo.lif.yaml
ENV PYTHONUNBUFFERED=1

# Long-running AMQP->plan->VDA5050 service; one-shot planning demo available
# via: uv run --no-sync python examples/blue_ocean_mapf_demo.py
CMD ["uv", "run", "--no-sync", "python", "examples/blue_ocean_planner_service.py"]
