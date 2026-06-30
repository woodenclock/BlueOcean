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

#ifndef VDA5050_CORE__MASTER__VALIDATION__SCHEMA_VALIDATOR_HPP_
#define VDA5050_CORE__MASTER__VALIDATION__SCHEMA_VALIDATOR_HPP_

#include "vda5050_core/order_utils/validation_result.hpp"
#include "vda5050_core/types/connection.hpp"
#include "vda5050_core/types/factsheet.hpp"
#include "vda5050_core/types/instant_actions.hpp"
#include "vda5050_core/types/order.hpp"
#include "vda5050_core/types/state.hpp"
#include "vda5050_core/types/visualization.hpp"

namespace vda5050_core::master {

// =============================================================================
// Schema validation — VDA5050 protocol-shape checks (Task #23).
// =============================================================================
//
// Lightweight C++ field-level checks complementary to (but not replacing) the
// JSON-level guarantees that vda5050_json_utils + ProtocolAdapter already
// provide: JSON parse errors and bad enum strings are caught upstream during
// deserialization. These validators run on the typed struct AFTER
// deserialization and verify protocol-required structural invariants:
//   • header.version is a member of SupportedSchemaVersions
//   • header.manufacturer + header.serial_number are non-empty
//   • message-specific required string fields (order_id, action_id, etc.)
//     are non-empty
//
// What these validators do NOT do:
//   • Graph topology (released ordering, edge counts) — Task #11
//   • Factsheet capability (action AGV supports, array-len limits) — Task #12
//   • AGV readiness (connection ONLINE, position initialized) — Task #16
//   • Action conflict — Task #22
//   • Cross-field consistency between, e.g., action_states and node_states.
//
// All overloads return a ValidationResult: empty on success, populated with
// SchemaValidationError-typed entries on failure. Free functions, no state —
// safe to call concurrently.

/**
 * @brief Validate an outgoing Order's schema before publish.
 *
 * Used by OrderPublisher::publish() as the first link of the validator
 * chain. Failure short-circuits the publish.
 */
vda5050_core::order_utils::ValidationResult validate_order_schema(
  const vda5050_core::types::Order& order);

/**
 * @brief Validate an outgoing InstantActions' schema before publish.
 */
vda5050_core::order_utils::ValidationResult validate_instant_actions_schema(
  const vda5050_core::types::InstantActions& actions);

/**
 * @brief Validate an incoming State message's schema.
 *
 * Used by AGV::handle_state() before caching. Failure causes the caller
 * to drop the message (no cache update, no callback).
 */
vda5050_core::order_utils::ValidationResult validate_state_schema(
  const vda5050_core::types::State& state);

/**
 * @brief Validate an incoming Connection message's schema.
 */
vda5050_core::order_utils::ValidationResult validate_connection_schema(
  const vda5050_core::types::Connection& connection);

/**
 * @brief Validate an incoming Factsheet message's schema.
 */
vda5050_core::order_utils::ValidationResult validate_factsheet_schema(
  const vda5050_core::types::Factsheet& factsheet);

/**
 * @brief Validate an incoming Visualization message's schema.
 */
vda5050_core::order_utils::ValidationResult validate_visualization_schema(
  const vda5050_core::types::Visualization& visualization);

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__VALIDATION__SCHEMA_VALIDATOR_HPP_
