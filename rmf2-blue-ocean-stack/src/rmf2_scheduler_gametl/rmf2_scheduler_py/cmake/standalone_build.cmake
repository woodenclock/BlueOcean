# Standalone pybind build for non-ROS Docker images.
# Invoked via: cmake -DRMF2_SCHEDULER_PY_STANDALONE=ON

find_package(rmf2_scheduler REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 REQUIRED)
find_package(pybind11_json REQUIRED)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra")
endif()

include_directories(include)

pybind11_add_module(core
  src/cache/action.cpp
  src/cache/event_action.cpp
  src/cache/process_action.cpp
  src/cache/series_action.cpp
  src/cache/schedule_cache.cpp
  src/cache/task_action.cpp
  src/core.cpp
  src/data/duration.cpp
  src/data/edge.cpp
  src/data/event.cpp
  src/data/graph.cpp
  src/data/node.cpp
  src/data/process.cpp
  src/data/task.cpp
  src/data/series.cpp
  src/data/occurrence.cpp
  src/data/time.cpp
  src/data/time_window.cpp
  src/data/schedule_action.cpp
  src/data/schedule_change_record.cpp
  src/executor_data.cpp
  src/process_executor.cpp
  src/process_executor_taskflow.cpp
  src/py_utils.cpp
  src/scheduler.cpp
  src/scheduler_options.cpp
  src/storage/schedule_stream.cpp
  src/system_time_executor.cpp
  src/task_executor.cpp
  src/task_executor_manager.cpp
  src/utils/tree_converter.cpp
)

target_link_libraries(core
  PRIVATE
    nlohmann_json::nlohmann_json
    pybind11_json
  PUBLIC
    rmf2_scheduler::rmf2_scheduler
)

if(APPLE)
  set(origin_token "@loader_path")
else()
  set(origin_token "$ORIGIN")
endif()
set_property(TARGET core PROPERTY INSTALL_RPATH "${origin_token}")

target_include_directories(core
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c
    "import sysconfig; print(sysconfig.get_path('purelib'))"
  OUTPUT_VARIABLE PYTHON_SITE_PACKAGES
  OUTPUT_STRIP_TRAILING_WHITESPACE
)

install(TARGETS core
  DESTINATION "${PYTHON_SITE_PACKAGES}/rmf2_scheduler"
)

install(
  DIRECTORY rmf2_scheduler/
  DESTINATION "${PYTHON_SITE_PACKAGES}/rmf2_scheduler"
  FILES_MATCHING
    PATTERN "*.py"
    PATTERN "*.pyi"
)
