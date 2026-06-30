/*
 * Copyright (C) 2026 ROS-Industrial Consortium Asia Pacific
 * Advanced Remanufacturing and Technology Centre
 * A*STAR Research Entities (Co. Registration No. 199702110H)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef VDA5050_CORE__MASTER__VALIDATION__FACTSHEET_ALIGNMENT_HPP_
#define VDA5050_CORE__MASTER__VALIDATION__FACTSHEET_ALIGNMENT_HPP_

#include <cstdint>
#include <string>
#include <vector>

#include "vda5050_core/master/map/map.hpp"
#include "vda5050_core/types/factsheet.hpp"

namespace vda5050_core::master {

// =============================================================================
// Factsheet alignment validator (Task #39, sub-criterion #2).
// =============================================================================
//
// Cross-checks a loaded `Map` against an AGV's factsheet.
// Implements the BACKLOG sub-criterion "Map is aligned with the AGV
// maps" (requirements.txt:71).
//
// **Symmetric trigger** (per design plan §6): the master invokes this
// at TWO events to keep the alignment cache fresh:
//   1. After successfully loading a map — refreshes against every
//      currently-onboarded AGV's last cached factsheet.
//   2. On `on_factsheet` callback — refreshes for the AGV whose
//      factsheet just arrived, against the currently-loaded map.
//
// **V0 rule set (concrete):**
//
//   "SpeedExceedsCapability" (ERROR)
//       For each map edge that declared `max_speed`, check
//       `factsheet.physical_parameters.speed_max >= edge.max_speed`.
//       If violated, the AGV physically cannot traverse the edge at the
//       integrator-required speed. This is the primary load-bearing
//       alignment check.
//
// **Rules deferred** (Critic feedback C1, see plan §V0 deferrals D):
//
//   - Footprint-fits-edge: V0 schema has no edge widths.
//   - Localization tolerance vs AGV localization precision: no
//     factsheet field expresses localization precision in v2.0.0.
//   - mapId / mapVersion match between factsheet and loaded map:
//     v2.0.0 factsheet does not carry a mapId field. Deferred to
//     v2.1.0 epic; runtime State.maps[] can be checked instead but
//     that is order-time, not factsheet-time.
//
// **Severity policy**: ERROR findings are surfaced loudly via
// VDA5050_ERROR logging on every assign_order against the affected AGV
// (see master.cpp wiring) but do NOT block onboarding — the FMS can
// still send orders; the integrator must fix either the map or the
// AGV's reported capability. This is intentional: bricking a fleet on a
// single map config error has worse failure modes than letting orders
// proceed with loud warnings.

/**
 * @brief Severity level for an alignment finding. Matches
 *        AgvAlignmentFinding.msg constants 1:1.
 */
enum class AlignmentSeverity : std::uint8_t
{
  WARNING = 0,
  ERROR = 1,
};

/**
 * @brief Single finding from check_factsheet_alignment. `code` is a
 *        stable identifier (see hpp doc-comment for the V0 list);
 *        `description` is human-readable and includes offending values.
 */
struct AlignmentFinding
{
  AlignmentSeverity severity;
  std::string code;
  std::string description;
};

/**
 * @brief Aggregated result of one factsheet × map alignment check.
 *        Always present in the master's per-AGV alignment cache; an
 *        empty `findings` vector means the AGV is fully aligned.
 */
struct FactsheetAlignmentResult
{
  std::vector<AlignmentFinding> findings;

  /**
   * @brief True iff any finding has severity ERROR. Convenience flag
   *        used by FMS clients (via GetLoadedMap.srv) and by master-
   *        side logging.
   */
  bool has_error() const;
};

/**
 * @brief Run alignment checks for `factsheet` against `map`. Stateless
 *        free function — safe to call concurrently. Returns a
 *        result with one finding per detected mismatch; empty findings
 *        means full alignment.
 */
FactsheetAlignmentResult check_factsheet_alignment(
  const Map& map, const vda5050_core::types::Factsheet& factsheet);

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__VALIDATION__FACTSHEET_ALIGNMENT_HPP_
