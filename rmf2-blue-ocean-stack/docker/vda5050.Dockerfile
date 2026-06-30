FROM ros:jazzy-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        python3-rosdep \
        ros-jazzy-rmw-cyclonedds-cpp \
        cmake \
        clang \
        libssl-dev \
        curl \
        ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV VDA_WS=/vda_ws
ENV VDA5050_PY=vda5050_core_gametl/vda5050_core_py
WORKDIR ${VDA_WS}/src

COPY src/vda5050_core_gametl/ vda5050_core_gametl/
COPY maps/map_transform/ /opt/gametl/maps/map_transform/
ENV PYTHONPATH=/opt/gametl/maps:${PYTHONPATH}

WORKDIR ${VDA_WS}
RUN apt-get update \
  && rosdep install --from-paths src --ignore-src --rosdistro=$ROS_DISTRO -y \
  && rm -rf /var/lib/apt/lists/*

ENV MAKEFLAGS=-j2
ENV CMAKE_BUILD_PARALLEL_LEVEL=2
RUN . /opt/ros/$ROS_DISTRO/setup.sh \
  && nice -n 19 ionice -c 3 colcon build --symlink-install 

# Ensure the colcon-built extension module is present for uv packaging (.so only;
# pyi/__init__ already live in the source tree; symlink-install shares paths).
RUN . /vda_ws/install/setup.sh \
  && VDA5050_PKG="$(python3 -c "import pathlib, vda5050_core_py; print(pathlib.Path(vda5050_core_py.__file__).parent)")" \
  && DEST=${VDA_WS}/src/${VDA5050_PY}/vda5050_core_py \
  && for so in "${VDA5050_PKG}"/_core.cpython-*.so; do \
       [ -e "$so" ] || continue; \
       [ "$so" -ef "$DEST/$(basename "$so")" ] || cp -a "$so" "$DEST/"; \
     done

WORKDIR ${VDA_WS}/src/${VDA5050_PY}/demo-june-blue-ocean
RUN uv sync

COPY docker/vda5050-master-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ARG VDA5050_PORT=8000
ENV VDA5050_PORT=${VDA5050_PORT}
EXPOSE ${VDA5050_PORT}
ENTRYPOINT ["/entrypoint.sh"]
