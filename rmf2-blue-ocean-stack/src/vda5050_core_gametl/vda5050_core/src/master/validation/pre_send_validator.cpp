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

#include "vda5050_core/master/validation/pre_send_validator.hpp"

#include <string>

#include "vda5050_core/errors/error_codes.hpp"
#include "vda5050_core/errors/error_factory.hpp"

namespace vda5050_core::master {

namespace {

const char* agv_state_name(AGVState state)
{
  switch (state)
  {
    case AGVState::STATE_UNKNOWN:
      return "STATE_UNKNOWN";
    case AGVState::AVAILABLE:
      return "AVAILABLE";
    case AGVState::UNAVAILABLE:
      return "UNAVAILABLE";
    case AGVState::ERROR:
      return "ERROR";
  }
  return "UNKNOWN";
}

}  // namespace

vda5050_core::order_utils::ValidationResult validate_pre_send(
  const PreSendContext& ctx)
{
  vda5050_core::order_utils::ValidationResult res;

  auto add_error = [&](const std::string& description) {
    res.errors.push_back(vda5050_core::errors::create_error(
      vda5050_core::errors::PreSendValidationError, description, {}));
  };

  // No-map gate (Task #39): the master cannot validate Order or Instant
  // Action node/edge identifiers against a topology it has not loaded.
  // Hard-reject — fail fast on missing config rather than silently
  // bypass map-integrity checks downstream.
  if (ctx.loaded_map == nullptr)
  {
    res.errors.push_back(vda5050_core::errors::create_error(
      vda5050_core::errors::MapValidationError,
      "Master has no map loaded — call load_map_from_config() before "
      "publishing.",
      {}));
    return res;  // remaining checks are meaningless without a map
  }

  // Connection ONLINE — practical guard; sending to OFFLINE / CONNECTIONBROKEN
  // is wasted MQTT.
  if (ctx.connection_status != vda5050_core::types::ConnectionState::ONLINE)
  {
    add_error("AGV connection_status is not ONLINE");
  }

  // Master-internal operational state. Only AVAILABLE is fit to receive
  // orders; ERROR / STATE_UNKNOWN / UNAVAILABLE are all rejected (fail-safe
  // — any future state is rejected by default).
  if (ctx.operational_state != AGVState::AVAILABLE)
  {
    add_error(
      std::string("AGV operational_state is not AVAILABLE (") +
      agv_state_name(ctx.operational_state) + ")");
  }

  // Need a State message before we can reason about mode or position.
  if (!ctx.last_state.has_value())
  {
    add_error("AGV has not yet reported any State");
    return res;  // remaining checks need last_state
  }

  // AUTOMATIC and SEMIAUTOMATIC both have the master in control; the other
  // modes (MANUAL / SERVICE / TEACHIN) do not.
  if (
    ctx.last_state->operating_mode !=
      vda5050_core::types::OperatingMode::AUTOMATIC &&
    ctx.last_state->operating_mode !=
      vda5050_core::types::OperatingMode::SEMIAUTOMATIC)
  {
    add_error("AGV operating_mode is not AUTOMATIC or SEMIAUTOMATIC");
  }

  if (ctx.last_state->paused.value_or(false))
  {
    add_error("AGV is paused");
  }

  if (ctx.last_state->safety_state.e_stop != vda5050_core::types::EStop::NONE)
  {
    add_error("AGV e-stop is engaged");
  }

  // Per VM-VDA-6-6-1-3 (BACKLOG): reject when AGV's position is not
  // initialized.
  if (
    !ctx.last_state->agv_position.has_value() ||
    !ctx.last_state->agv_position->position_initialized)
  {
    add_error("AGV position is not initialized");
  }

  return res;
}

}  // namespace vda5050_core::master
