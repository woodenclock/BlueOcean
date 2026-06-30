# Copyright 2025 ROS Industrial Consortium Asia Pacific
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Find or install Taskflow
#

macro(find_taskflow)
  find_package(Taskflow QUIET)

  # Trying vendor first
  if(NOT Taskflow_FOUND)
    message(STATUS "Trying taskflow_vendor Ament CMake package")

    if(USE_AMENT_VENDOR_EXTERNAL)
      find_package(taskflow_vendor QUIET)
      if(NOT taskflow_vendor_FOUND)
        message(STATUS "taskflow_vendor not found")
      endif()
    endif()
  endif()

  # Use CPM next
  if(NOT Taskflow_FOUND)
    if(USE_CPM_EXTERNAL)
      cpmaddpackage(
        NAME Taskflow
        GITHUB_REPOSITORY taskflow/taskflow
        GIT_TAG v3.11.0
        EXCLUDE_FROM_ALL YES
        OPTIONS
          "TF_BUILD_TESTS OFF"
          "TF_BUILD_EXAMPLES OFF"
      )

      if(Taskflow_ADDED AND TARGET Taskflow::Taskflow)
        message(STATUS "CPM added Taskflow")
        set(Taskflow_FOUND TRUE)
      endif()
    endif()
  endif()

  if(NOT Taskflow_FOUND)
    message(FATAL_ERROR "Taskflow not found")
  endif()
endmacro()
