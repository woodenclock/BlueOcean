FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app/res_mapf

COPY src/res_mapf_gametl/res_mapf /app/res_mapf
# No map/robot data is baked in: the planner service fetches its topology and
# robot profiles from the VDA5050 master (/map/grid, /robots) at startup — the
# master is the single source of truth (depends_on keeps it healthy first).

# Plan-server stack only (res_mapf_planning + res_plan_execution +
# res_plan_server); skips res_pybullet so no simulator/ROS deps.
RUN uv sync --package res_plan_server --no-dev \
    && uv pip install rich pika paho-mqtt

ENV PYTHONUNBUFFERED=1

# Long-running AMQP->plan->VDA5050 service (fetches map/robots from the master).
# The one-shot standalone demo (examples/blue_ocean_mapf_demo.py) reads files
# instead, so it needs ./maps mounted or is better run locally from the repo.
CMD ["uv", "run", "--no-sync", "python", "examples/blue_ocean_planner_service.py"]
