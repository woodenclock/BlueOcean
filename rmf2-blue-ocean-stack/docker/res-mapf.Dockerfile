FROM ros:jazzy-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        python3-vcstool \
        python3-rosdep \
        python3-pip \
        python3-dev \
        ros-jazzy-rmw-cyclonedds-cpp \
        libgl1 \
        libglib2.0-0 \
  && pip3 install --no-cache-dir uv --break-system-packages \
  && rm -rf /var/lib/apt/lists/*

ENV RES_WS=/res_ws
WORKDIR ${RES_WS}/src

COPY src/res_mapf_gametl/ res_mapf_gametl/

# Import upstream dependencies (res_mapf, next_gen_prototype)
RUN vcs import --input res_mapf_gametl/deps.repos .

WORKDIR ${RES_WS}
RUN apt-get update \
  && rosdep install --from-paths src --ignore-src --rosdistro=$ROS_DISTRO -y \
  && rm -rf /var/lib/apt/lists/*

ENV MAKEFLAGS=-j2
ENV CMAKE_BUILD_PARALLEL_LEVEL=2
RUN . /opt/ros/$ROS_DISTRO/setup.sh \
  && nice -n 19 ionice -c 3 colcon build --packages-select res_ros2_msgs res_ros2

RUN sed -i '$isource "/res_ws/install/setup.bash"' /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["ros2", "run", "res_ros2", "plan_server_node"]
