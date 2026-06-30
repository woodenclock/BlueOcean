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

#ifndef VDA5050_CORE__MASTER__VALIDATION__TRAVERSABILITY_VALIDATOR_HPP_
#define VDA5050_CORE__MASTER__VALIDATION__TRAVERSABILITY_VALIDATOR_HPP_

#include "vda5050_core/master/validation/pre_send_validator.hpp"
#include "vda5050_core/order_utils/validation_result.hpp"
#include "vda5050_core/types/instant_actions.hpp"
#include "vda5050_core/types/order.hpp"

namespace vda5050_core::master {

// =============================================================================
// Traversability validation — can THIS AGV physically execute the message?
// =============================================================================
//
// Fourth link of the validator chain (after schema #23, PreSend #16, graph
// #11). Implements VM-VDA-6-6-1-3 acceptance criteria #1 (nodes/edges
// traversable by AGV) and #4 (first node trivially reachable), plus
// VM-VDA-6-6-4 #2 (master sends only actions the AGV supports).
//
// Three concerns covered:
//
//   1. **Reachability** — is the AGV at or near the order's first released
//      node? (state-driven; runs even when factsheet is missing)
//   2. **Action capability** — can the AGV perform every Action in the
//      Order/InstantActions, with the correct scope (NODE/EDGE/INSTANT)
//      and supported parameter keys? (factsheet-driven)
//   3. **Array-size limits** — does the message fit within the AGV's
//      protocol_limits.max_array_lens? (factsheet-driven)
//
// **Skip-when-factsheet-missing**: factsheet-dependent checks (capability
// + limits) skip silently when ctx.last_factsheet has no value. The
// reachability check still runs (uses state, not factsheet). The publisher
// caller may choose to log a WARN that traversability ran without
// factsheet — see AGV::publish_order/publish_instant_actions.
//
// Two overloads (Order and InstantActions) because the rules differ:
// reachability + nested array limits apply to Order; only action
// capability + top-level instant_actions array limit applies to
// InstantActions.

/**
 * @brief Validate that an outgoing Order is traversable by the AGV
 *        described by the snapshot's factsheet.
 *
 * Used by OrderPublisher::publish() as the fourth chain link.
 */
vda5050_core::order_utils::ValidationResult validate_traversability(
  const PreSendContext& ctx, const vda5050_core::types::Order& order);

/**
 * @brief Validate that an outgoing InstantActions message is supported
 *        by the AGV described by the snapshot's factsheet.
 *
 * Used by InstantActionsPublisher::publish() as the third chain link
 * (broadens architecture doc, which originally had no traversability link
 * for InstantActions; the action-capability sub-check is shared with
 * Order's per-action validation).
 */
vda5050_core::order_utils::ValidationResult validate_traversability(
  const PreSendContext& ctx,
  const vda5050_core::types::InstantActions& actions);

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__VALIDATION__TRAVERSABILITY_VALIDATOR_HPP_
