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

#ifndef VDA5050_CORE__MASTER__MAP__MAP_HPP_
#define VDA5050_CORE__MASTER__MAP__MAP_HPP_

#include <chrono>
#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace vda5050_core::master {

// =============================================================================
// Master-side topology map (Task #39).
// =============================================================================
//
// In-memory representation of the warehouse / floor map the master operates
// on. Loaded once from a JSON config file at startup (see map_loader.hpp).
//
// **Why not reuse vda5050_core::types::Node / Edge?**
//   Those types carry Order semantics: sequence_id, released, actions[] —
//   meaningful only inside an Order. A static topology node has only
//   identity + geometry. Keeping the master's topology types separate from
//   the Order-wire types is the cleanest separation of concerns.
//
// **Why MapInfo mirrors vda5050_types state-side Map fields?**
//   VDA5050 v2.0.0 §6.3.2 / §7.8 defines the State.maps[] entry as
//   (mapId, mapVersion, mapStatus, optional mapDescriptor). MapInfo uses
//   the same field set so the master can echo it later in State payloads
//   without an intermediate wrapper.
//
// **Wire-format note for reviewers**: MapEdge.bidirectional / max_speed /
//   length are **master-side topology config**, not VDA5050 v2.0.0 wire
//   fields. The spec's Edge type lives on Orders; this type is the static
//   pre-deployed topology. Don't search the spec for these fields — they
//   are intentionally master-internal.

/**
 * @brief State of a map at runtime — mirrors VDA5050 v2.0.0 §6.3.2
 *        State.maps[].mapStatus enum.
 */
enum class MapStatus : std::uint8_t
{
  ENABLED = 0,
  DISABLED = 1,
};

/**
 * @brief Metadata identifying a loaded map. Field set mirrors VDA5050
 *        v2.0.0 State.maps[] for direct echo compatibility.
 */
struct MapInfo
{
  std::string map_id;
  std::string map_version;
  MapStatus map_status = MapStatus::ENABLED;
  std::string map_descriptor;  ///< Optional human-readable name.
};

/**
 * @brief Static topology node — identity + geometry only.
 *
 * Optional fields (theta, allowed_deviation_*) follow VDA5050
 * NodePosition optionality so the loader can be lenient when integrators
 * omit them. `map_description` mirrors NodePosition.mapDescription
 * (per-node, distinct from MapInfo.map_descriptor).
 */
struct MapNode
{
  std::string node_id;
  double x = 0.0;
  double y = 0.0;
  std::optional<double> theta;
  std::optional<double> allowed_deviation_xy;
  std::optional<double> allowed_deviation_theta;
  std::string map_description;
};

/**
 * @brief Static topology edge connecting two MapNodes.
 *
 * `bidirectional` defaults to false (an edge must explicitly opt in to
 * reverse traversal). `max_speed` and `length` are optional — integrators
 * may omit either, in which case the corresponding factsheet-alignment /
 * length-consistency check is skipped for that edge.
 */
struct MapEdge
{
  std::string edge_id;
  std::string start_node_id;
  std::string end_node_id;
  bool bidirectional = false;
  std::optional<double> max_speed;  ///< [m/s] — integrator-declared limit.
  std::optional<double> length;     ///< [m]   — path length end-to-end.
};

/**
 * @brief Full loaded map: metadata + topology + O(1) lookup helpers.
 *
 * The lookup tables (`node_index` / `edge_index`) are populated by the
 * loader after parsing nodes / edges, mapping id → vector index. They
 * are part of the public type so validators (traversability map-
 * integrity, factsheet alignment) can do constant-time existence checks.
 *
 * `loaded_at` and `source_path` are diagnostic bookkeeping — surfaced
 * via GetLoadedMap.srv for FMS operator visibility.
 */
struct Map
{
  MapInfo info;
  std::vector<MapNode> nodes;
  std::vector<MapEdge> edges;

  // O(1) lookup helpers populated by the loader post-parse.
  std::unordered_map<std::string, std::size_t> node_index;
  std::unordered_map<std::string, std::size_t> edge_index;

  // Bookkeeping.
  std::chrono::system_clock::time_point loaded_at;
  std::string source_path;  ///< Empty when loaded from in-memory JSON.

  /**
   * @brief Look up a node by id. Returns nullptr if not present.
   */
  const MapNode* find_node(const std::string& id) const;

  /**
   * @brief Look up an edge by id. Returns nullptr if not present.
   */
  const MapEdge* find_edge(const std::string& id) const;
};

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__MAP__MAP_HPP_
