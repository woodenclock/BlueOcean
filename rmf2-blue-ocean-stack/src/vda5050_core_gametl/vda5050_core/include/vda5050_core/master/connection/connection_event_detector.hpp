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

#ifndef VDA5050_CORE__MASTER__CONNECTION__CONNECTION_EVENT_DETECTOR_HPP_
#define VDA5050_CORE__MASTER__CONNECTION__CONNECTION_EVENT_DETECTOR_HPP_

#include <optional>

#include "vda5050_core/types/connection.hpp"

namespace vda5050_core::master {

/**
 * @brief Classification of a Connection-state transition between two
 *        consecutive Connection messages.
 *
 * Three connectionState values map to three distinct
 * master-observable events:
 *
 *   - `CONNECTED`         — AGV transitioned to ONLINE (initial connect
 *                           or reconnect after recovery).
 *   - `OFFLINE`           — AGV transitioned to OFFLINE — the AGV
 *                           explicitly published this state before a
 *                           graceful MQTT DISCONNECT. **No last-will
 *                           involved.**
 *   - `CONNECTIONBROKEN`  — Broker auto-published the AGV's pre-registered
 *                           last-will message because the AGV's TCP
 *                           connection unexpectedly dropped. **This is
 *                           the last-will firing.**
 *
 * Note: the last-will message has stale `timestamp` and
 * `headerId` fields because they were registered at AGV connect time;
 * don't trust them as the actual disconnect time.
 */
enum class ConnectionEventKind
{
  NONE,              ///< No transition this update (sustained state).
  CONNECTED,         ///< Transitioned to ONLINE.
  OFFLINE,           ///< Transitioned to OFFLINE (graceful).
  CONNECTIONBROKEN,  ///< Transitioned to CONNECTIONBROKEN (last-will).
};

/**
 * @brief Edge-detect a Connection-state transition between prev and curr.
 *
 * Returns non-NONE only when curr's `connection_state` differs from
 * prev's (or prev is absent — first message). Sustained states return
 * NONE so callers don't fire reaction logic repeatedly.
 *
 * @param prev Previous Connection message, or nullopt if none yet.
 * @param curr Current Connection message just received.
 */
ConnectionEventKind detect_connection_transition(
  const std::optional<vda5050_core::types::Connection>& prev,
  const vda5050_core::types::Connection& curr);

}  // namespace vda5050_core::master

#endif  // VDA5050_CORE__MASTER__CONNECTION__CONNECTION_EVENT_DETECTOR_HPP_
