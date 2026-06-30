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

#ifndef VDA5050_CORE__MASTER__VALIDATION__INSTANT_ACTION_MODE_VALIDATOR_HPP_
#define VDA5050_CORE__MASTER__VALIDATION__INSTANT_ACTION_MODE_VALIDATOR_HPP_

#include <string>

#include "vda5050_core/master/validation/pre_send_validator.hpp"
#include "vda5050_core/order_utils/validation_result.hpp"
#include "vda5050_core/types/instant_actions.hpp"

namespace vda5050_core::master {

// =============================================================================
// Per-action-type operating-mode gate for instant actions.
// =============================================================================
//
// Reconciles two parts of VDA5050 v2.0.0:
//
//   - §6.10.6 (lines 3693-3713): Master Control should not send "driving
//     order or actions" to the AGV in MANUAL / SERVICE / TEACHIN modes.
//   - §6.8.1: defines instant-scope predefined actions (initPosition,
//     cancelOrder, stateRequest, factsheetRequest, startPause, stopPause,
//     startCharging, stopCharging, logReport) whose use cases are
//     inherently non-AUTOMATIC (bootstrap, recovery, diagnostic, control).
//
// Resolution: the §6.10.6 prohibition is enforced for all *operational*
// actions, but the §6.8.1 instant-scope actions are exempt because they
// are precisely the actions designed for those modes.
//
// **Allowlist** (per §6.8.1 predefined instant-scope actions):
//   stateRequest, factsheetRequest, logReport, cancelOrder, initPosition,
//   startPause, stopPause, startCharging, stopCharging
//
// **Behavior**:
//   - last_state has no value: pass (degraded mode, mirrors PreSend posture)
//   - operating_mode == AUTOMATIC or SEMIAUTOMATIC: pass (master in control)
//   - else: each action's action_type must be in the allowlist; otherwise
//     reject (§6.10.6 violation).
//
// Returns errors with `PreSendValidationError` type (the relevant master-
// internal validation category — the gate is a master pre-send concern,
// not a structural or conflict concern). The first failing action
// short-circuits.
//
// Note: SEMIAUTOMATIC is treated like AUTOMATIC because §6.10.6 says
// SEMIAUTOMATIC has master "in control" (HMI affects speed only).

vda5050_core::order_utils::ValidationResult validate_instant_action_mode(
  const PreSendContext& ctx,
  const vda5050_core::types::InstantActions& actions);

/// Test/inspection helper: true if the given action_type is on the
/// non-AUTOMATIC allowlist. Spec §6.8.1 predefined instant-scope actions.
bool is_mode_exempt_action_type(const std::string& action_type);

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__VALIDATION__INSTANT_ACTION_MODE_VALIDATOR_HPP_
