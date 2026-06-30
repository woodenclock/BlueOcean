#!/bin/bash
set -eo pipefail

source /opt/ros/${ROS_DISTRO}/setup.bash
source /vda_ws/install/setup.bash

cd /vda_ws/src/vda5050_core_gametl/vda5050_core_py/demo-june-blue-ocean
uv sync

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec uv run python example_master_webserver.py
