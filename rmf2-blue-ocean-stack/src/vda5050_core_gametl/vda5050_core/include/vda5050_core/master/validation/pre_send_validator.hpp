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

#ifndef VDA5050_CORE__MASTER__VALIDATION__PRE_SEND_VALIDATOR_HPP_
#define VDA5050_CORE__MASTER__VALIDATION__PRE_SEND_VALIDATOR_HPP_

#include <memory>
#include <optional>

#include "vda5050_core/master/agv.hpp"
#include "vda5050_core/master/map/map.hpp"
#include "vda5050_core/order_utils/validation_result.hpp"
#include "vda5050_core/types/connection_state.hpp"
#include "vda5050_core/types/factsheet.hpp"
#include "vda5050_core/types/order.hpp"
#include "vda5050_core/types/state.hpp"

namespace vda5050_core::master {

// =============================================================================
// PreSend validation — AGV readiness gate (Task #16).
// =============================================================================
//
// Second link in the validator chain, after schema validation (#23) and
// before graph (#11) / traversability (#12) / action-conflict (#22). Used by
// both OrderPublisher and InstantActionsPublisher with the same readiness
// rules.
//
// Per VDA5050 v2.0.0 §6.10 (operatingMode descriptions), the master should
// only send orders/actions to an AGV that is under master control (AUTOMATIC
// mode) and has reported an initialized position. Connection ONLINE and
// non-ERROR operational state are master-side practical guards.
//
// **Snapshot semantics**: PreSendContext is a stack-local POD struct populated
// once by the AGV under its existing locks (state_mutex_ + data_mutex_), then
// passed to this validator lock-free. Race-safe by construction — the
// snapshot is immutable for the duration of the validate_pre_send() call.

/**
 * @brief AGV readiness snapshot captured under AGV mutexes once, validated
 *        lock-free.
 *
 * Carries every cached AGV value the publisher chain validators may need
 * (PreSend #16, traversability #12, future #14 stitching). Despite the
 * "PreSend" name, this struct is the AGV-snapshot carrier for the entire
 * outgoing-publish chain.
 */
struct PreSendContext
{
  /// Most recent connection_state observed (from connection topic).
  vda5050_core::types::ConnectionState connection_status;

  /// Last cached State message (nullopt if AGV has not yet reported state).
  std::optional<vda5050_core::types::State> last_state;

  /// Last cached Factsheet message (nullopt if AGV has not yet reported a
  /// factsheet). Used by traversability validation (#12) for AGV capability
  /// + array-limit checks. PreSend (#16) does not use this field.
  std::optional<vda5050_core::types::Factsheet> last_factsheet;

  /// Master-internal AGV operational state (UNAVAILABLE on connection loss,
  /// ERROR on AGV-reported errors, AVAILABLE while a State message has been
  /// observed within the heartbeat window).
  AGVState operational_state;

  /// Last successfully published Order for this AGV, or nullopt if no
  /// active order is being tracked. Used by OrderPublisher's structural
  /// validation step to detect "is this an update?" — when set and
  /// `active_order->order_id == candidate.order_id`, the chain runs
  /// `is_valid_update(active, candidate)` instead of `is_valid_graph`.
  /// Built from `OrderLifecycleManager::snapshot()` at publish time.
  /// Always nullopt for InstantActions (instant actions aren't updates).
  std::optional<vda5050_core::types::Order> active_order;

  /// Master's currently-loaded topology map (Task #39). Captured under
  /// the master's `map_mutex_` at publish time and held for the
  /// duration of the validator chain. May be nullptr when no map has
  /// been loaded yet — pre_send_validator hard-rejects in that case
  /// (master cannot route Orders against a topology it has not
  /// loaded). traversability_validator's map_integrity sub-check uses
  /// this snapshot to verify Order node/edge IDs.
  std::shared_ptr<const Map> loaded_map;
};

/**
 * @brief Validate AGV readiness for outgoing publish.
 *
 * Returns empty ValidationResult on success. On failure, returns one or more
 * PreSendValidationError entries — non-fatal preconditions accumulate so the
 * caller sees ALL pending issues at once. (Exception: missing last_state
 * short-circuits, since downstream mode/position checks would be unreachable.)
 *
 * Used by OrderPublisher::publish() and InstantActionsPublisher::publish() as
 * the second link in the validator chain. Stateless free function — safe to
 * call concurrently.
 */
vda5050_core::order_utils::ValidationResult validate_pre_send(
  const PreSendContext& ctx);

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__VALIDATION__PRE_SEND_VALIDATOR_HPP_
