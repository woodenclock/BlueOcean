cmake_minimum_required(VERSION 3.5)

project(rmf2_scheduler VERSION 0.2.0)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra")
endif()

option(USE_AMENT_VENDOR_EXTERNAL "Use thirdparty dependencies packaged as ament vendor package" ON)
option(USE_CPM_EXTERNAL "Use CPM to download and install thirdparty dependencies" ON)
option(BUILD_TESTING "Build tests" ON)

file(GLOB CMAKE_FILES "${CMAKE_CURRENT_SOURCE_DIR}/cmake/*.cmake")
message(STATUS ${CMAKE_FILES})
foreach(CMAKE_FILE ${CMAKE_FILES})
  include(${CMAKE_FILE})
endforeach()

find_package(Boost REQUIRED)
find_package(nlohmann_json REQUIRED)

find_croncpp()
find_taskflow()

include(GNUInstallDirs)

add_library(${PROJECT_NAME}
  SHARED
  src/cache/action.cpp
  src/cache/event_action.cpp
  src/cache/task_action.cpp
  src/cache/task_handler.cpp
  src/cache/process_action.cpp
  src/cache/process_handler.cpp
  src/cache/series_action.cpp
  src/cache/series_handler.cpp
  src/cache/schedule_cache.cpp
  src/data/duration.cpp
  src/data/time.cpp
  src/data/node.cpp
  src/data/graph.cpp
  src/data/schedule_action.cpp
  src/data/schedule_change_record.cpp
  src/data/series.cpp
  src/default_log_handler.cpp
  src/executor_data.cpp
  src/http/curl_api.cpp
  src/http/common.cpp
  src/http/connection_curl.cpp
  src/http/connection_fake.cpp
  src/http/memory_stream.cpp
  src/http/request.cpp
  src/http/transport.cpp
  src/http/transport_curl.cpp
  src/http/transport_fake.cpp
  src/log.cpp
  src/process_executor_taskflow.cpp
  src/scheduler.cpp
  src/scheduler_options.cpp
  src/storage/schedule_stream.cpp
  src/storage/schedule_stream_ld_broker.cpp
  src/storage/schedule_stream_simple.cpp
  src/system_time_executor.cpp
  src/task_executor_manager.cpp
  src/time_window_lookup.cpp
  src/utils/dag_helper.cpp
  src/utils/data_encoding.cpp
  src/utils/string_utils.cpp
  src/utils/tree_converter.cpp
  src/utils/url_utils.cpp
)

target_link_libraries(${PROJECT_NAME}
  PRIVATE
    nlohmann_json::nlohmann_json
    croncpp::croncpp
    Taskflow::Taskflow
    curl
    tinyxml2
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/>
)
target_compile_definitions(${PROJECT_NAME}
  PUBLIC
  BOOST_DLL_USE_STD_FS
)

add_library(${PROJECT_NAME}::${PROJECT_NAME} ALIAS ${PROJECT_NAME})

add_executable(dag_to_bt
  examples/dag_to_bt.cpp
)

target_link_libraries(dag_to_bt
  ${PROJECT_NAME}
)

add_executable(rs_http_request
  examples/rs_http_request.cpp
)

target_link_libraries(rs_http_request
  ${PROJECT_NAME}
)

add_executable(ld_broker_crud
  examples/ld_broker_crud.cpp
)

target_link_libraries(ld_broker_crud
  ${PROJECT_NAME}
)

add_executable(create_sample_backups
  examples/create_sample_backups.cpp
)

target_link_libraries(create_sample_backups
  ${PROJECT_NAME}
)

add_executable(clear_ld_broker
  examples/clear_ld_broker.cpp
)

target_link_libraries(clear_ld_broker
  ${PROJECT_NAME}
)

add_executable(run_scheduler
  examples/run_scheduler.cpp
)

target_link_libraries(run_scheduler
  ${PROJECT_NAME}
)

find_package(ament_cmake_gtest QUIET)
if(NOT ament_cmake_gtest_FOUND)
  message(WARNING "ament_cmake_gtest not found, testing is disabled")
  set(BUILD_TESTING OFF)
endif()

if(BUILD_TESTING)
  find_package(ament_cmake_cpplint REQUIRED)
  find_package(ament_cmake_uncrustify REQUIRED)
  find_package(ament_cmake_xmllint REQUIRED)
  find_package(ament_cmake_copyright REQUIRED)
  find_package(ament_cmake_lint_cmake REQUIRED)

  ament_copyright()
  ament_cpplint()
  ament_lint_cmake(CMakeLists.txt ./cmake/*.cmake ./cmake/*.cmake.in)
  ament_uncrustify()
  ament_xmllint()

  add_subdirectory(test)
endif()

install(TARGETS
  ${PROJECT_NAME}
  EXPORT ${PROJECT_NAME}-targets
  LIBRARY DESTINATION lib
)

install(TARGETS
  dag_to_bt
  rs_http_request
  ld_broker_crud
  clear_ld_broker
  run_scheduler
  create_sample_backups
  DESTINATION lib/${PROJECT_NAME}
)

install(
  DIRECTORY include/
  DESTINATION include
)

set(INSTALL_CONFIG_DIR "${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_NAME}")
set(PACKAGE_CONFIG_VERSION_FILE "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}ConfigVersion.cmake")
set(PACKAGE_CONFIG_FILE "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}Config.cmake")

install(
  EXPORT ${PROJECT_NAME}-targets
  FILE ${PROJECT_NAME}Targets.cmake
  NAMESPACE ${PROJECT_NAME}::
  DESTINATION ${INSTALL_CONFIG_DIR}
)

include(CMakePackageConfigHelpers)

configure_package_config_file(
  "cmake/${PROJECT_NAME}Config.cmake.in"
  ${PACKAGE_CONFIG_FILE}
  INSTALL_DESTINATION ${INSTALL_CONFIG_DIR}
)

write_basic_package_version_file(
  ${PACKAGE_CONFIG_VERSION_FILE}
  COMPATIBILITY SameMajorVersion
)

install(
  FILES
    ${PACKAGE_CONFIG_VERSION_FILE}
    ${PACKAGE_CONFIG_FILE}
  DESTINATION ${INSTALL_CONFIG_DIR}
)

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/share/ament_index/resource_index/packages/${PROJECT_NAME} "")
install(
  FILES ${CMAKE_CURRENT_BINARY_DIR}/share/ament_index/resource_index/packages/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages
)

file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/share/${PROJECT_NAME}/hook/ament_prefix_path.dsv "prepend-non-duplicate;AMENT_PREFIX_PATH;")
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/share/${PROJECT_NAME}/hook/ament_prefix_path.dsv DESTINATION share/${PROJECT_NAME}/hook)
