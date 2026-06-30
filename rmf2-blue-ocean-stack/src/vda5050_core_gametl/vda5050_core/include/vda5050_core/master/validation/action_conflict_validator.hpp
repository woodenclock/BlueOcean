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

#ifndef VDA5050_CORE__MASTER__VALIDATION__ACTION_CONFLICT_VALIDATOR_HPP_
#define VDA5050_CORE__MASTER__VALIDATION__ACTION_CONFLICT_VALIDATOR_HPP_

#include "vda5050_core/master/validation/pre_send_validator.hpp"
#include "vda5050_core/order_utils/validation_result.hpp"
#include "vda5050_core/types/instant_actions.hpp"

namespace vda5050_core::master {

// =============================================================================
// Action conflict validation — does THIS instantAction collide with the AGV's
// running actions or driving state? (Task #22)
// =============================================================================
//
// Final link of the InstantActionsPublisher chain (after schema #23,
// PreSend #16, traversability #12). Implements
// VM-VDA-6-9-1 #2 [BACKLOG]: "Ensure that instant action does not conflict
// with AGV's current order" — using §6.12 blocking_type semantics as the
// conflict algorithm.
//
// Conflict model (V0, base blocking_type only — per-action-type exemptions
// arrive with #17 cancelOrder + #18 pause/resume):
//
//   - NONE   blocking_type: always allowed
//   - SOFT   blocking_type: rejected if state.driving == true
//   - HARD   blocking_type: rejected if any active action in
//            state.action_states[] (status WAITING / INITIALIZING /
//            RUNNING / PAUSED) OR state.driving == true
//
// **Active-action set**: WAITING / INITIALIZING / RUNNING / PAUSED.
// FINISHED / FAILED are non-active. PAUSED is included conservatively
// because mid-pause HARD execution could collide on resume.
//
// **No-state degraded mode**: if ctx.last_state has no value (AGV never
// reported state), no active state is known and no conflicts are possible.
// Pass through. This matches the PreSend validator's degraded behaviour.
//
// **Known V0 limitation**: cancelOrder, startPause, stopPause are typically
// HARD-blocking and are designed to interrupt running state. Under this
// validator's base rule they will be rejected during driving or while
// active actions are present. This is spec-correct per §6.12 but
// operationally awkward. The exemptions land with #17 / #18. Until then,
// FMS authors that genuinely need to bypass can call the lower-level
// `master.publish_instant_actions(...)` (skips the sync pre-flight).

/**
 * @brief Validate that a candidate InstantActions message does not
 *        conflict with the AGV's currently-running actions or driving
 *        state.
 *
 * Returns errors with type
 * `vda5050_core::errors::ActionConflictValidationError`. The error
 * description encodes which rule fired so callers can classify into
 * fine-grained decision codes:
 *   - "HARD_ACTION_BLOCKED" — HARD candidate vs active actions
 *   - "ACTION_BLOCKED_BY_DRIVING" — SOFT/HARD candidate vs driving
 *
 * The first failing action short-circuits and returns immediately.
 *
 * Used by InstantActionsPublisher::publish() (async chain) and
 * VDA5050Master::assign_instant_actions (sync caller-visible).
 */
vda5050_core::order_utils::ValidationResult validate_action_conflict(
  const PreSendContext& ctx,
  const vda5050_core::types::InstantActions& actions);

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__VALIDATION__ACTION_CONFLICT_VALIDATOR_HPP_
