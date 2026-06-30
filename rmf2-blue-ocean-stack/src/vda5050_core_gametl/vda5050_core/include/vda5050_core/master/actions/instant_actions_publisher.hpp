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

#ifndef VDA5050_CORE__MASTER__ACTIONS__INSTANT_ACTIONS_PUBLISHER_HPP_
#define VDA5050_CORE__MASTER__ACTIONS__INSTANT_ACTIONS_PUBLISHER_HPP_

#include "vda5050_core/execution/protocol_adapter.hpp"
#include "vda5050_core/order_utils/validation_result.hpp"
#include "vda5050_core/types/instant_actions.hpp"

namespace vda5050_core::master {

// Forward-declared to avoid pulling agv.hpp (transitive cycle) into this
// header. Definition lives in vda5050_core/master/validation/pre_send_validator.hpp.
struct PreSendContext;

/**
 * @brief Publisher for VDA5050 InstantActions messages.
 *
 * Stateless wrapper that mirrors OrderPublisher. The validator chain
 * for instant actions (PreSendValidator, ActionConflictDetector) will
 * plug in here without changing the publish() signature.
 *
 * Threading: stateless — safe to call concurrently. The underlying
 * MqttClientInterface (held by ProtocolAdapter) coordinates its own
 * threading.
 */
class InstantActionsPublisher
{
public:
  InstantActionsPublisher() = default;

  /**
   * @brief Publish an InstantActions message through the supplied adapter.
   * @param adapter Per-AGV typed adapter (caller-owned).
   * @param ctx     AGV readiness snapshot for PreSend gate (#16). Built by
   *                the caller (typically AGV) under its own locks.
   * @param actions The instant actions message to publish.
   * @return ValidationResult — empty errors vector means success.
   *
   * Validator chain: schema (#23) → PreSend (#16) → (future) action conflict
   * (#22) → adapter.publish.
   */
  vda5050_core::order_utils::ValidationResult publish(
    vda5050_core::execution::ProtocolAdapter& adapter,
    const PreSendContext& ctx,
    const vda5050_core::types::InstantActions& actions);
};

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__ACTIONS__INSTANT_ACTIONS_PUBLISHER_HPP_
