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

#include "vda5050_core/master/actions/instant_actions_publisher.hpp"

#include "vda5050_core/errors/error_codes.hpp"
#include "vda5050_core/errors/error_factory.hpp"
#include "vda5050_core/master/standard_names.hpp"
#include "vda5050_core/master/validation/action_conflict_validator.hpp"
#include "vda5050_core/master/validation/instant_action_mode_validator.hpp"
#include "vda5050_core/master/validation/pre_send_validator.hpp"
#include "vda5050_core/master/validation/schema_validator.hpp"
#include "vda5050_core/master/validation/traversability_validator.hpp"

namespace vda5050_core::master {

vda5050_core::order_utils::ValidationResult InstantActionsPublisher::publish(
  vda5050_core::execution::ProtocolAdapter& adapter, const PreSendContext& ctx,
  const vda5050_core::types::InstantActions& actions)
{
  // Validator chain: schema (#23) → ONLINE check → instant-action mode
  // gate (§6.10.6 + §6.8.1 allowlist) → traversability (#12, capability
  // sub-check) → action conflict (#22). Each link short-circuits on
  // failure.
  //
  // **Why no full PreSend (#16) for instant actions**: PreSend's strict
  // checks (operational_state != ERROR, operating_mode == AUTOMATIC,
  // position_initialized) are order-centric. Instant actions are designed
  // to function in those degraded states (cancelOrder during ERROR,
  // initPosition before position is initialized, factsheetRequest with
  // no prior state). Running full PreSend here would silently drop
  // actions that the sync `assign_instant_actions` pre-flight intentionally
  // let through.
  //
  // We retain TWO targeted defenses inline:
  //   1. ONLINE check: QoS 0 silent drops to OFFLINE AGV are unobservable.
  //   2. Mode gate: §6.10.6 says master must not send actions in
  //      MANUAL/SERVICE/TEACHIN, BUT §6.8.1 defines instant-scope
  //      predefined actions designed for those modes. The gate enforces
  //      the §6.10.6 prohibition with a §6.8.1 allowlist exemption.
  auto schema_result = validate_instant_actions_schema(actions);
  if (!schema_result)
  {
    return schema_result;
  }

  if (ctx.connection_status != vda5050_core::types::ConnectionState::ONLINE)
  {
    vda5050_core::order_utils::ValidationResult res;
    res.errors.push_back(vda5050_core::errors::create_error(
      vda5050_core::errors::PreSendValidationError,
      "AGV connection_status is not ONLINE", {}));
    return res;
  }

  auto mode_result = validate_instant_action_mode(ctx, actions);
  if (!mode_result)
  {
    return mode_result;
  }

  auto traversability_result = validate_traversability(ctx, actions);
  if (!traversability_result)
  {
    return traversability_result;
  }

  auto conflict_result = validate_action_conflict(ctx, actions);
  if (!conflict_result)
  {
    return conflict_result;
  }

  adapter.publish<vda5050_core::types::InstantActions>(
    actions, static_cast<int>(InstantActionsQos));

  return vda5050_core::order_utils::ValidationResult{};  // success
}

}  // namespace vda5050_core::master
