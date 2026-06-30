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

#include "vda5050_core/master/validation/action_conflict_validator.hpp"

#include <string>
#include <vector>

#include "vda5050_core/errors/error_codes.hpp"
#include "vda5050_core/errors/error_factory.hpp"

namespace vda5050_core::master {

namespace {

using ::vda5050_core::errors::ActionConflictValidationError;
using ::vda5050_core::errors::create_error;
using ::vda5050_core::errors::RefActionId;
using ::vda5050_core::order_utils::ValidationResult;
using ::vda5050_core::types::ActionStatus;
using ::vda5050_core::types::BlockingType;
using ::vda5050_core::types::ErrorReference;

// Stable diagnostic keywords embedded in error_description so callers
// (master.assign_instant_actions) can map errors back to fine-grained
// InstantActionDecision cases by substring lookup. Kept here as the single
// source of truth.
constexpr const char* kKeyHardBlocked = "HARD_ACTION_BLOCKED";
constexpr const char* kKeyBlockedByDriving = "ACTION_BLOCKED_BY_DRIVING";

// VDA5050 v2.0.0 §6.10.6 action_status values that mean "AGV is currently
// committed to this action and master must not start a HARD action in
// parallel". FINISHED / FAILED are non-active. PAUSED is conservative —
// included because mid-pause HARD execution could collide on resume.
constexpr bool is_active_status(ActionStatus s)
{
  return s == ActionStatus::WAITING || s == ActionStatus::INITIALIZING ||
         s == ActionStatus::RUNNING || s == ActionStatus::PAUSED;
}

}  // namespace

ValidationResult validate_action_conflict(
  const PreSendContext& ctx, const vda5050_core::types::InstantActions& actions)
{
  ValidationResult res;

  auto add_error =
    [&](const std::string& description, std::vector<ErrorReference> refs) {
      res.errors.push_back(
        create_error(ActionConflictValidationError, description, refs));
    };

  // Degraded mode: if the AGV has not reported a State message, master
  // has no view of action_states or driving. Pass through — same posture
  // as PreSend validator's no-state branch.
  if (!ctx.last_state.has_value()) return res;

  const auto& state = ctx.last_state.value();
  const bool driving = state.driving;

  // Pre-compute "any active action present" for the HARD path.
  bool any_active = false;
  for (const auto& as : state.action_states)
  {
    if (is_active_status(as.action_status))
    {
      any_active = true;
      break;
    }
  }

  for (const auto& action : actions.actions)
  {
    switch (action.blocking_type)
    {
      case BlockingType::NONE:
        // Always allowed (§6.12: parallel + driving OK).
        break;
      case BlockingType::SOFT:
        if (driving)
        {
          add_error(
            std::string(kKeyBlockedByDriving) + ": SOFT-blocking action '" +
              action.action_type +
              "' rejected because AGV is driving (§6.12: vehicle must "
              "not drive)",
            {{RefActionId, action.action_id}});
          return res;
        }
        break;
      case BlockingType::HARD:
        if (driving)
        {
          add_error(
            std::string(kKeyBlockedByDriving) + ": HARD-blocking action '" +
              action.action_type +
              "' rejected because AGV is driving (§6.12: vehicle must "
              "not drive)",
            {{RefActionId, action.action_id}});
          return res;
        }
        if (any_active)
        {
          add_error(
            std::string(kKeyHardBlocked) + ": HARD-blocking action '" +
              action.action_type +
              "' rejected because AGV has active actions in flight "
              "(§6.12: must not be executed in parallel)",
            {{RefActionId, action.action_id}});
          return res;
        }
        break;
    }
  }

  return res;
}

}  // namespace vda5050_core::master
