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

#ifndef VDA5050_CORE__MASTER__MAP__MAP_LOADER_HPP_
#define VDA5050_CORE__MASTER__MAP__MAP_LOADER_HPP_

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "vda5050_core/master/map/map.hpp"

namespace vda5050_core::master {

// =============================================================================
// JSON map config loader (Task #39, sub-criterion #1).
// =============================================================================
//
// V0 scope: load ONE topology map from a JSON config file at master
// startup. No v2.1.0 map-server distribution, no hot reload, no multi-
// map active simultaneously — the API shape supports those retrofits but
// they are intentionally out-of-V0 (see vda5050_doc/task/task39_*.md).
//
// **Lenient on unknown fields**: nlohmann::json silently ignores keys
// the loader doesn't read, so integrators can add forward-compat fields
// (e.g. v2.1.0 mapDownloadLink) without breaking the master.
//
// **What the loader validates**:
//   - File can be opened + parsed as JSON.
//   - Top-level `map_info`, `nodes[]`, `edges[]` present.
//   - `nodes[]` non-empty.
//   - Each node has `node_id`, `x`, `y`.
//   - Each edge has `edge_id`, `start_node_id`, `end_node_id`.
//   - No duplicate node_ids / edge_ids.
//   - Every edge's start_node_id / end_node_id refers to a known node.
//
// **What the loader does NOT validate** (handled elsewhere or deferred):
//   - Compatibility with any AGV factsheet — see factsheet_alignment.hpp
//     (sub-criterion #2).
//   - Length / euclidean-distance consistency — out of V0 (would require
//     deciding whether curved paths are first-class).

/**
 * @brief Categorical error type for `MapLoadError`. Stable identifiers
 *        for surfacing in logs / diagnostics.
 */
enum class MapLoadErrorType : std::uint8_t
{
  FILE_NOT_FOUND,
  FILE_READ_FAILED,
  JSON_PARSE_ERROR,
  MISSING_REQUIRED_FIELD,
  INVALID_FIELD_VALUE,
  DUPLICATE_NODE_ID,
  DUPLICATE_EDGE_ID,
  DANGLING_EDGE_REF,
  EMPTY_MAP,
};

/**
 * @brief Single loader error with a categorical type + a human-readable
 *        description that includes the offending id / path / value.
 */
struct MapLoadError
{
  MapLoadErrorType type;
  std::string description;
};

/**
 * @brief Result of a load attempt.
 *
 * On success: `map` is populated and `errors` is empty (the bool
 * conversion is true).
 *
 * On failure: `map` is `nullopt`, `errors` carries one or more entries.
 * The loader accumulates errors where reasonable (e.g. multiple
 * duplicate ids) so callers see all problems at once, but gives up early
 * on file-level errors (FILE_NOT_FOUND, JSON_PARSE_ERROR).
 */
struct MapLoadResult
{
  std::optional<Map> map;
  std::vector<MapLoadError> errors;

  explicit operator bool() const
  {
    return errors.empty() && map.has_value();
  }
};

/**
 * @brief Load a map from a JSON file at `path`. Sets `Map.source_path`
 *        on success. Errors include FILE_NOT_FOUND / FILE_READ_FAILED if
 *        the file is unreadable.
 */
MapLoadResult load_from_file(const std::string& path);

/**
 * @brief Load a map from an already-parsed JSON value. Used by
 *        `load_from_file` after parse, and directly by tests.
 *
 * @param json         Parsed JSON object — must be an object.
 * @param source_path  Optional bookkeeping path stored on
 *                     `Map.source_path`. Empty for in-memory loads.
 */
MapLoadResult load_from_json(
  const nlohmann::json& json, const std::string& source_path = "");

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__MAP__MAP_LOADER_HPP_
