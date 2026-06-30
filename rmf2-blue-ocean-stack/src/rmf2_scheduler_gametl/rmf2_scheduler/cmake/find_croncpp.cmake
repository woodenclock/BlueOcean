# Copyright 2026 ROS Industrial Consortium Asia Pacific
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
# Find or Install croncpp package.
#

macro(find_croncpp)
  find_package(croncpp QUIET)

  # Trying vendor first
  if(NOT croncpp_FOUND)
    message(STATUS "Trying croncpp_vendor Ament CMake package")

    if(USE_AMENT_VENDOR_EXTERNAL)
      find_package(croncpp_vendor QUIET)
      if(NOT croncpp_vendor_FOUND)
        message(STATUS "croncpp_vendor not found")
      endif()
    endif()
  endif()

  # Use CPM next
  if(NOT croncpp_FOUND)
    if(USE_CPM_EXTERNAL)
      cpmaddpackage(
        NAME croncpp
        PATCHES ${CMAKE_CURRENT_SOURCE_DIR}/cmake/croncpp.patch
        GITHUB_REPOSITORY mariusbancila/croncpp
        GIT_TAG v2023.03.30
        EXCLUDE_FROM_ALL YES
        OPTIONS
          "CRONCPP_BUILD_TESTS OFF"
          "CRONCPP_BUILD_BENCHMARK OFF"
      )

      if(croncpp_ADDED AND TARGET croncpp::croncpp)
        message(STATUS "CPM added croncpp")
        set(croncpp_FOUND TRUE)
      endif()
    endif()
  endif()

  if(NOT croncpp_FOUND)
    message(FATAL_ERROR "croncpp not found")
  endif()
endmacro()
