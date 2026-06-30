/*
 * Copyright (C) 2025 ROS-Industrial Consortium Asia Pacific
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

#include "vda5050_core/master/master.hpp"

#include <chrono>
#include <cstdint>
#include <set>
#include <sstream>
#include <utility>
#include <vector>

#include "nlohmann/json.hpp"
#include "vda5050_core/errors/error_codes.hpp"
#include "vda5050_core/errors/error_factory.hpp"
#include "vda5050_core/execution/protocol_adapter.hpp"
#include "vda5050_core/json_utils/serialization.hpp"
#include "vda5050_core/logger/logger.hpp"
#include "vda5050_core/master/order/order_stitcher.hpp"
#include "vda5050_core/master/standard_names.hpp"
#include "vda5050_core/master/validation/action_conflict_validator.hpp"
#include "vda5050_core/master/validation/factsheet_alignment.hpp"
#include "vda5050_core/master/validation/instant_action_mode_validator.hpp"
#include "vda5050_core/master/validation/pre_send_validator.hpp"

namespace vda5050_core::master {

// ============================================================================
// Constructor / Destructor
// ============================================================================

VDA5050Master::VDA5050Master(
  std::shared_ptr<vda5050_core::transport::MqttClientInterface> mqtt_client)
: mqtt_client_(std::move(mqtt_client))
{
  VDA5050_INFO("[VDA5050Master] Created VDA5050Master instance");

  // Wire broker connection-state callbacks (Task #70). The destructor
  // unregisters these before disconnect() so they cannot fire on a
  // partially-destroyed master. Capturing `this` is safe under that
  // ordering — the MQTT client never invokes a cleared callback.
  if (mqtt_client_)
  {
    mqtt_client_->set_connection_lost_callback(
      [this](const std::string& cause) {
        this->handle_broker_connection_lost(cause);
      });
    mqtt_client_->set_connected_callback([this](const std::string& cause) {
      this->handle_broker_connected(cause);
    });
  }
}

VDA5050Master::~VDA5050Master()
{
  VDA5050_INFO("[VDA5050Master] Destroying VDA5050Master instance");
  // Unregister the connection-state callbacks before disconnecting so
  // they cannot fire on a partially-destroyed master (Task #70).
  if (mqtt_client_)
  {
    mqtt_client_->set_connection_lost_callback(nullptr);
    mqtt_client_->set_connected_callback(nullptr);
  }
  disconnect();

  // Stop AGV worker threads BEFORE agvs_ is destructed at the end of
  // this body. Each AGV's queue-processor thread can call back into
  // this master (e.g. get_loaded_map()) via parent_raw_; that pointer
  // must remain valid for the lifetime of any in-flight publish. By
  // joining queue threads here — synchronously, while *this is still
  // fully alive — we guarantee no AGV thread is mid-call into the
  // master when the rest of the master's members destruct.
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);
    for (auto& kv : agvs_)
    {
      if (kv.second)
      {
        kv.second->stop();
      }
    }
  }
  VDA5050_INFO("[VDA5050Master] VDA5050Master instance destroyed");
}

// ============================================================================
// Connection Management
// ============================================================================

void VDA5050Master::connect()
{
  if (!mqtt_client_)
  {
    VDA5050_WARN("[VDA5050Master] Cannot connect: no MQTT client");
    return;
  }

  if (mqtt_client_->connected())
  {
    VDA5050_WARN("[VDA5050Master] Already connected");
    return;
  }

  VDA5050_INFO("[VDA5050Master] Connecting MQTT client");
  mqtt_client_->connect();
}

void VDA5050Master::disconnect()
{
  if (!mqtt_client_)
  {
    return;
  }

  if (!mqtt_client_->connected())
  {
    return;
  }

  VDA5050_INFO("[VDA5050Master] Disconnecting MQTT client");
  mqtt_client_->disconnect();
  VDA5050_INFO("[VDA5050Master] Disconnected");
}

bool VDA5050Master::is_connected() const
{
  return mqtt_client_ && mqtt_client_->connected();
}

// ============================================================================
// AGV Onboarding/Offboarding
// ============================================================================

std::shared_ptr<AGV> VDA5050Master::create_agv_locked_(
  const std::string& manufacturer, const std::string& serial_number,
  std::size_t max_queue_size, bool drop_oldest)
{
  // weak_from_this() back-ref lets the AGV dispatch into our virtuals
  // and detect master destruction. Caller wires MQTT subscriptions
  // separately, outside `agv_mutex_`, to avoid a deadlock where Paho's
  // network thread fires an inbound `on_state` callback that needs the
  // master mutex while the subscribing thread is still inside SUBSCRIBE.
  return std::make_shared<AGV>(
    vda5050_core::execution::ProtocolAdapter::make(
      mqtt_client_, InterfaceName, Version, manufacturer, serial_number),
    manufacturer, serial_number, max_queue_size, drop_oldest,
    StateHeartbeatInterval, weak_from_this());
}

void VDA5050Master::onboard_agv(
  const std::string& manufacturer, const std::string& serial_number,
  size_t max_queue_size, bool drop_oldest)
{
  std::string agv_id = manufacturer + "/" + serial_number;

  std::shared_ptr<AGV> new_agv;
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);

    if (get_agv_by_id(agv_id))
    {
      VDA5050_WARN("[VDA5050Master] AGV already onboarded: {}", agv_id);
      return;
    }

    new_agv = create_agv_locked_(
      manufacturer, serial_number, max_queue_size, drop_oldest);
    agvs_[agv_id] = new_agv;
  }

  // MQTT SUBSCRIBE blocks on SUBACK; if a PUBLISH races in on Paho's
  // network thread it will dispatch on_state -> get_agv() which needs
  // agv_mutex_. Wire subscriptions outside the lock.
  new_agv->setup_subscriptions();

  VDA5050_INFO("[VDA5050Master] Onboarded AGV: {}", agv_id);
}

VDA5050Master::BatchOnboardResult VDA5050Master::onboard_agv_batch(
  const std::vector<OnboardSpec>& specs)
{
  BatchOnboardResult result;
  std::vector<std::shared_ptr<AGV>> new_agvs;

  {
    std::lock_guard<std::mutex> lock(agv_mutex_);

    for (const auto& spec : specs)
    {
      if (spec.manufacturer.empty() || spec.serial_number.empty())
      {
        result.failed.push_back(spec);
        VDA5050_WARN(
          "[VDA5050Master] onboard_agv_batch: empty manufacturer or serial "
          "rejected");
        continue;
      }

      const std::string agv_id = spec.manufacturer + "/" + spec.serial_number;
      if (agvs_.find(agv_id) != agvs_.end())
      {
        result.skipped_already_onboarded.push_back(spec);
        continue;
      }

      auto agv = create_agv_locked_(
        spec.manufacturer, spec.serial_number, spec.max_queue_size,
        spec.drop_oldest);
      agvs_[agv_id] = agv;
      new_agvs.push_back(std::move(agv));
      result.onboarded.push_back(spec);
    }
  }

  // Wire MQTT subscriptions outside agv_mutex_ — see onboard_agv() for
  // the deadlock this avoids.
  for (auto& agv : new_agvs) agv->setup_subscriptions();

  VDA5050_INFO(
    "[VDA5050Master] onboard_agv_batch: onboarded={} skipped={} failed={}",
    result.onboarded.size(), result.skipped_already_onboarded.size(),
    result.failed.size());
  return result;
}

std::size_t VDA5050Master::offboard_agv_batch(
  const std::vector<std::pair<std::string, std::string>>& keys)
{
  // AGV::stop() joins the queue thread; gather under the lock and
  // stop outside, same as offboard_agv().
  std::vector<std::shared_ptr<AGV>> to_stop;
  to_stop.reserve(keys.size());
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);
    for (const auto& key : keys)
    {
      if (key.first.empty() || key.second.empty()) continue;
      const std::string agv_id = key.first + "/" + key.second;
      auto it = agvs_.find(agv_id);
      if (it == agvs_.end()) continue;
      if (it->second) to_stop.push_back(std::move(it->second));
      agvs_.erase(it);
    }
  }

  {
    std::lock_guard<std::mutex> lock(assignments_mutex_);
    for (const auto& key : keys)
    {
      if (key.first.empty() || key.second.empty()) continue;
      active_assignments_.erase(key.first + "/" + key.second);
    }
  }

  for (auto& agv : to_stop)
  {
    if (agv) agv->stop();
  }

  VDA5050_INFO(
    "[VDA5050Master] offboard_agv_batch: offboarded={}", to_stop.size());
  return to_stop.size();
}

std::vector<std::pair<std::string, std::string>>
VDA5050Master::get_onboarded_agvs() const
{
  std::lock_guard<std::mutex> lock(agv_mutex_);
  std::vector<std::pair<std::string, std::string>> out;
  out.reserve(agvs_.size());
  for (const auto& kv : agvs_)
  {
    const std::string& agv_id = kv.first;
    const auto slash = agv_id.find('/');
    if (slash == std::string::npos)
    {
      out.emplace_back(agv_id, std::string{});
    }
    else
    {
      out.emplace_back(agv_id.substr(0, slash), agv_id.substr(slash + 1));
    }
  }
  return out;
}

void VDA5050Master::offboard_agv(
  const std::string& manufacturer, const std::string& serial_number)
{
  std::string agv_id = manufacturer + "/" + serial_number;

  std::shared_ptr<AGV> agv;
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);
    auto it = agvs_.find(agv_id);
    if (it == agvs_.end())
    {
      VDA5050_WARN(
        "[VDA5050Master] Cannot offboard: AGV not found: {}", agv_id);
      return;
    }
    agv = std::move(it->second);
    agvs_.erase(it);
  }

  // Stop AGV after removing from map. The AGV destructor calls
  // protocol_adapter_->unsubscribe<T>() for each subscribed topic, so
  // the broker stops routing to lambdas captured at subscribe time
  // before the AGV instance is gone.
  agv->stop();

  {
    std::lock_guard<std::mutex> lock(assignments_mutex_);
    active_assignments_.erase(agv_id);
  }

  VDA5050_INFO("[VDA5050Master] Offboarded AGV: {}", agv_id);
}

void VDA5050Master::record_assignment(
  const std::string& manufacturer, const std::string& serial_number,
  const std::string& assignment_id, const std::string& order_id,
  std::uint32_t order_update_id)
{
  const std::string agv_id = manufacturer + "/" + serial_number;
  std::lock_guard<std::mutex> lock(assignments_mutex_);
  if (assignment_id.empty())
  {
    active_assignments_.erase(agv_id);
    return;
  }
  active_assignments_[agv_id] =
    ActiveAssignment{assignment_id, order_id, order_update_id};
}

std::string VDA5050Master::get_active_assignment_id(
  const std::string& manufacturer, const std::string& serial_number) const
{
  const std::string agv_id = manufacturer + "/" + serial_number;
  std::lock_guard<std::mutex> lock(assignments_mutex_);
  auto it = active_assignments_.find(agv_id);
  if (it == active_assignments_.end()) return {};
  return it->second.assignment_id;
}

void VDA5050Master::clear_assignment(
  const std::string& manufacturer, const std::string& serial_number)
{
  const std::string agv_id = manufacturer + "/" + serial_number;
  std::lock_guard<std::mutex> lock(assignments_mutex_);
  active_assignments_.erase(agv_id);
}

bool VDA5050Master::is_agv_onboarded(
  const std::string& manufacturer, const std::string& serial_number) const
{
  std::lock_guard<std::mutex> lock(agv_mutex_);
  std::string agv_id = manufacturer + "/" + serial_number;
  return get_agv_by_id(agv_id) != nullptr;
}

// ============================================================================
// AGV Access
// ============================================================================

std::shared_ptr<AGV> VDA5050Master::get_agv(
  const std::string& manufacturer, const std::string& serial_number) const
{
  std::lock_guard<std::mutex> lock(agv_mutex_);
  std::string agv_id = manufacturer + "/" + serial_number;
  return get_agv_by_id(agv_id);
}

std::shared_ptr<AGV> VDA5050Master::get_agv_by_id(
  const std::string& agv_id) const
{
  // Note: Caller must hold agv_mutex_
  auto it = agvs_.find(agv_id);
  return (it != agvs_.end()) ? it->second : nullptr;
}

// ============================================================================
// Outgoing Messages
// ============================================================================

bool VDA5050Master::publish_order(
  const std::string& manufacturer, const std::string& serial_number,
  const vda5050_core::types::Order& order)
{
  std::string agv_id = manufacturer + "/" + serial_number;

  std::shared_ptr<AGV> agv;
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);
    agv = get_agv_by_id(agv_id);
  }

  if (!agv)
  {
    throw std::runtime_error(
      "Cannot publish order: AGV not onboarded: " + agv_id);
  }

  return agv->send_order(order);
}

AssignmentResult VDA5050Master::assign_order(
  const std::string& manufacturer, const std::string& serial_number,
  const vda5050_core::types::Order& order)
{
  AssignmentResult res;
  auto add_error = [&](const std::string& description) {
    res.errors.push_back(vda5050_core::errors::create_error(
      vda5050_core::errors::PreSendValidationError, description, {}));
  };

  // Step 1: AGV lookup.
  const std::string agv_id = manufacturer + "/" + serial_number;
  std::shared_ptr<AGV> agv;
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);
    agv = get_agv_by_id(agv_id);
  }
  if (!agv)
  {
    res.decision = AssignmentDecision::AGV_NOT_ONBOARDED;
    add_error("AGV not onboarded: " + agv_id);
    return res;
  }

  // Step 2: connection ONLINE (VM-VDA-6-14-1).
  if (
    agv->get_connection_status() !=
    vda5050_core::types::ConnectionState::ONLINE)
  {
    res.decision = AssignmentDecision::AGV_OFFLINE;
    add_error("AGV connection_status is not ONLINE");
    return res;
  }

  // Step 3: operational state AVAILABLE.
  if (agv->get_operational_state() != AGVState::AVAILABLE)
  {
    res.decision = AssignmentDecision::AGV_NOT_READY;
    add_error("AGV operational_state is not AVAILABLE");
    return res;
  }

  // Steps 4-5: state-derived checks.
  auto last_state = agv->get_last_state();
  if (!last_state.has_value())
  {
    res.decision = AssignmentDecision::AGV_NO_STATE_YET;
    add_error("AGV has not yet reported any State");
    return res;
  }
  if (
    last_state->operating_mode != vda5050_core::types::OperatingMode::AUTOMATIC)
  {
    res.decision = AssignmentDecision::AGV_MODE_NOT_AUTO;
    add_error("AGV operating_mode is not AUTOMATIC");
    return res;
  }
  if (
    !last_state->agv_position.has_value() ||
    !last_state->agv_position->position_initialized)
  {
    res.decision = AssignmentDecision::AGV_POSITION_NOT_INITIALIZED;
    add_error("AGV position is not initialized (VM-VDA-6-6-1-3 #7)");
    return res;
  }

  // Step 6: stitch pre-flight (only when this is an update for the
  // active order). Stateless; no shared state touched.
  //
  // We snapshot the stitcher decision for caller-visible feedback,
  // but always hand off to send_order on non-REJECT outcomes. The
  // queue-processor thread re-runs the stitcher (in AGV::publish_order)
  // and is the single owner of pending-queue enqueue. This avoids
  // duplicate enqueue + handles state drift between assign_order's
  // snapshot and the queue thread's later execution.
  const auto snap = agv->active_order_snapshot();
  bool stitch_will_queue = false;
  if (snap.has_active && snap.order_id == order.order_id)
  {
    OrderStitcher stitcher;
    auto stitch = stitcher.decide(order, snap);
    if (stitch.decision == StitchDecision::REJECT)
    {
      res.decision = AssignmentDecision::STITCH_REJECTED;
      res.errors = std::move(stitch.errors);
      return res;
    }
    stitch_will_queue = (stitch.decision == StitchDecision::QUEUE_PENDING);
  }

  // Step 7: hand off to async path. send_order returns false only on
  // outbound queue full.
  if (!agv->send_order(order))
  {
    res.decision = AssignmentDecision::AGV_NOT_READY;
    add_error("AGV outbound queue full or unable to accept order");
    return res;
  }
  res.decision = stitch_will_queue ? AssignmentDecision::STITCH_QUEUED
                                   : AssignmentDecision::ASSIGNED;
  return res;
}

bool VDA5050Master::publish_instant_actions(
  const std::string& manufacturer, const std::string& serial_number,
  const vda5050_core::types::InstantActions& actions)
{
  std::string agv_id = manufacturer + "/" + serial_number;

  std::shared_ptr<AGV> agv;
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);
    agv = get_agv_by_id(agv_id);
  }

  if (!agv)
  {
    throw std::runtime_error(
      "Cannot publish instant actions: AGV not onboarded: " + agv_id);
  }

  return agv->send_instant_actions(actions);
}

InstantActionAssignmentResult VDA5050Master::assign_instant_actions(
  const std::string& manufacturer, const std::string& serial_number,
  const vda5050_core::types::InstantActions& actions)
{
  InstantActionAssignmentResult res;
  auto add_error = [&](const std::string& description) {
    res.errors.push_back(vda5050_core::errors::create_error(
      vda5050_core::errors::PreSendValidationError, description, {}));
  };

  // Step 1: AGV lookup.
  const std::string agv_id = manufacturer + "/" + serial_number;
  std::shared_ptr<AGV> agv;
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);
    agv = get_agv_by_id(agv_id);
  }
  if (!agv)
  {
    res.decision = InstantActionDecision::AGV_NOT_ONBOARDED;
    add_error("AGV not onboarded: " + agv_id);
    return res;
  }

  // Step 2: connection ONLINE.
  if (
    agv->get_connection_status() !=
    vda5050_core::types::ConnectionState::ONLINE)
  {
    res.decision = InstantActionDecision::AGV_OFFLINE;
    add_error("AGV connection_status is not ONLINE");
    return res;
  }

  // Step 3: action_id uniqueness — within the batch, vs state's in-flight
  // action_states[], and vs the active order's node/edge actions.
  // §6.6.2 mandates global uniqueness; AGV behaviour on collision is
  // undefined across vendors.
  std::set<std::string> in_flight;
  if (auto last_state = agv->get_last_state(); last_state.has_value())
  {
    for (const auto& as : last_state->action_states)
    {
      in_flight.insert(as.action_id);
    }
  }
  const auto snap = agv->active_order_snapshot();
  if (snap.has_active)
  {
    for (const auto& n : snap.nodes)
    {
      for (const auto& a : n.actions) in_flight.insert(a.action_id);
    }
    for (const auto& e : snap.edges)
    {
      for (const auto& a : e.actions) in_flight.insert(a.action_id);
    }
  }
  std::set<std::string> seen_in_batch;
  for (const auto& a : actions.actions)
  {
    if (a.action_id.empty())
    {
      res.decision = InstantActionDecision::DUPLICATE_ACTION_ID;
      add_error("Action with empty action_id is not allowed");
      return res;
    }
    if (in_flight.count(a.action_id))
    {
      res.decision = InstantActionDecision::DUPLICATE_ACTION_ID;
      add_error(
        "action_id '" + a.action_id +
        "' collides with an in-flight action on the AGV");
      return res;
    }
    if (!seen_in_batch.insert(a.action_id).second)
    {
      res.decision = InstantActionDecision::DUPLICATE_ACTION_ID;
      add_error(
        "action_id '" + a.action_id + "' is duplicated within the batch");
      return res;
    }
  }

  // Step 4: operating-mode gate per §6.10.6 with §6.8.1 allowlist. Sync
  // mirror of the async validator so FMS sees AGV_MODE_NOT_AUTO_FOR_ACTION
  // immediately for non-exempt action_types in MANUAL/SERVICE/TEACHIN.
  PreSendContext mode_ctx{
    agv->get_connection_status(),
    agv->get_last_state(),
    agv->get_last_factsheet(),
    agv->get_operational_state(),
    std::nullopt /* active_order: instant actions are not order updates */,
    get_loaded_map()};
  auto mode_res = validate_instant_action_mode(mode_ctx, actions);
  if (!mode_res)
  {
    res.errors = std::move(mode_res.errors);
    res.decision = InstantActionDecision::AGV_MODE_NOT_AUTO_FOR_ACTION;
    return res;
  }

  // Step 5: action conflict pre-flight (Task #22). Mirror of the async
  // chain's conflict validator so FMS gets caller-visible feedback
  // before queue hand-off.
  PreSendContext conflict_ctx{
    agv->get_connection_status(),
    agv->get_last_state(),
    agv->get_last_factsheet(),
    agv->get_operational_state(),
    std::nullopt /* active_order: instant actions are not order updates */,
    get_loaded_map()};
  auto conflict_res = validate_action_conflict(conflict_ctx, actions);
  if (!conflict_res)
  {
    // Map error_description keyword to fine-grained decision case.
    // Stable keywords are defined in action_conflict_validator.cpp.
    res.errors = std::move(conflict_res.errors);
    const auto& first_desc =
      res.errors.front().error_description.value_or(std::string{});
    if (first_desc.find("HARD_ACTION_BLOCKED") != std::string::npos)
    {
      res.decision = InstantActionDecision::HARD_ACTION_BLOCKED;
    }
    else
    {
      res.decision = InstantActionDecision::ACTION_BLOCKED_BY_DRIVING;
    }
    return res;
  }

  // Step 6: hand off to async path. send_instant_actions returns false
  // only on outbound queue full.
  if (!agv->send_instant_actions(actions))
  {
    res.decision = InstantActionDecision::AGV_QUEUE_FULL;
    add_error("AGV outbound queue full or unable to accept instant actions");
    return res;
  }
  res.decision = InstantActionDecision::ASSIGNED;
  return res;
}

// ============================================================================
// User-Extension Callbacks — default empty implementations
// ============================================================================
//
// Override these in a subclass to react to incoming AGV messages.
// Default implementations are empty so a master that doesn't subclass
// still works silently.

void VDA5050Master::on_state(
  const std::string& /*agv_id*/, const vda5050_core::types::State& /*state*/)
{
}

void VDA5050Master::on_connection(
  const std::string& /*agv_id*/,
  const vda5050_core::types::Connection& /*connection*/)
{
}

void VDA5050Master::on_factsheet(
  const std::string& /*agv_id*/,
  const vda5050_core::types::Factsheet& /*factsheet*/)
{
}

// ============================================================================
// Topology Map (Task #39)
// ============================================================================

MapLoadResult VDA5050Master::load_map_from_config(const std::string& path)
{
  auto result = load_from_file(path);
  if (!result)
  {
    VDA5050_ERROR(
      "[VDA5050Master] Map config load failed for '{}': {} error(s)", path,
      result.errors.size());
    return result;
  }

  // Snapshot the new map into a shared_ptr<const Map>; install + refresh
  // alignment via set_map (which centralizes the symmetric trigger).
  set_map(*result.map);

  VDA5050_INFO(
    "[VDA5050Master] Loaded map '{}' v{} from '{}' ({} nodes, {} edges)",
    result.map->info.map_id, result.map->info.map_version, path,
    result.map->nodes.size(), result.map->edges.size());

  return result;
}

void VDA5050Master::set_map(Map map)
{
  // Snapshot AGVs first (lock order: agv → map). Snapshot the IDs +
  // shared_ptrs into a local copy so we can release agv_mutex_ before
  // doing factsheet IO + map_mutex_ work.
  std::vector<std::pair<std::string, std::shared_ptr<AGV>>> agvs_snapshot;
  {
    std::lock_guard<std::mutex> lock(agv_mutex_);
    agvs_snapshot.reserve(agvs_.size());
    for (const auto& kv : agvs_)
      agvs_snapshot.emplace_back(kv.first, kv.second);
  }

  auto installed = std::make_shared<const Map>(std::move(map));

  // Compute alignment for each AGV against the new map outside any
  // master lock — uses each AGV's own data_mutex_ via accessors.
  std::unordered_map<std::string, FactsheetAlignmentResult> new_cache;
  for (const auto& kv : agvs_snapshot)
  {
    const auto& fs_opt = kv.second->get_last_factsheet();
    if (!fs_opt.has_value()) continue;
    auto alignment = check_factsheet_alignment(*installed, fs_opt.value());
    new_cache.emplace(kv.first, std::move(alignment));
  }

  // Atomically install map + replace alignment cache.
  {
    std::lock_guard<std::mutex> lock(map_mutex_);
    active_map_ = installed;
    alignment_cache_ = std::move(new_cache);
  }
}

std::shared_ptr<const Map> VDA5050Master::get_loaded_map() const
{
  std::lock_guard<std::mutex> lock(map_mutex_);
  return active_map_;
}

std::unordered_map<std::string, FactsheetAlignmentResult>
VDA5050Master::get_alignment_cache_snapshot() const
{
  std::lock_guard<std::mutex> lock(map_mutex_);
  return alignment_cache_;
}

void VDA5050Master::refresh_alignment_for_agv(
  const std::string& agv_id, const vda5050_core::types::Factsheet& factsheet)
{
  std::shared_ptr<const Map> snap;
  {
    std::lock_guard<std::mutex> lock(map_mutex_);
    snap = active_map_;
  }
  if (snap == nullptr) return;  // no map loaded yet — nothing to align

  auto alignment = check_factsheet_alignment(*snap, factsheet);
  if (alignment.has_error())
  {
    VDA5050_ERROR(
      "[VDA5050Master] Factsheet alignment ERROR for AGV {} against map "
      "'{}': {} finding(s)",
      agv_id, snap->info.map_id, alignment.findings.size());
  }

  std::lock_guard<std::mutex> lock(map_mutex_);
  alignment_cache_[agv_id] = std::move(alignment);
}

void VDA5050Master::on_visualization(
  const std::string& /*agv_id*/,
  const vda5050_core::types::Visualization& /*visualization*/)
{
}

// ============================================================================
// Event triggers — empty default impls
// ============================================================================

void VDA5050Master::on_node_reached(
  const std::string& /*agv_id*/, const std::string& /*node_id*/)
{
}

void VDA5050Master::on_errors_appeared(
  const std::string& /*agv_id*/,
  const std::vector<vda5050_core::types::Error>& /*new_errors*/)
{
}

void VDA5050Master::on_errors_resolved(
  const std::string& /*agv_id*/,
  const std::vector<vda5050_core::types::Error>& /*resolved_errors*/)
{
}

void VDA5050Master::on_new_base_requested(const std::string& /*agv_id*/) {}

void VDA5050Master::on_mode_changed(
  const std::string& /*agv_id*/,
  vda5050_core::types::OperatingMode /*new_mode*/,
  vda5050_core::types::OperatingMode /*prev_mode*/)
{
}

void VDA5050Master::on_paused(const std::string& /*agv_id*/, bool /*paused*/) {}

void VDA5050Master::on_driving(const std::string& /*agv_id*/, bool /*driving*/)
{
}

void VDA5050Master::on_loads_changed(
  const std::string& /*agv_id*/,
  const std::vector<vda5050_core::types::Load>& /*loads*/)
{
}

void VDA5050Master::on_connect(const std::string& /*agv_id*/) {}

void VDA5050Master::on_offline(const std::string& /*agv_id*/) {}

void VDA5050Master::on_connection_broken(const std::string& /*agv_id*/) {}

void VDA5050Master::on_state_timeout(const std::string& /*agv_id*/) {}

void VDA5050Master::on_state_resumed(const std::string& /*agv_id*/) {}

void VDA5050Master::on_broker_disconnected() {}

void VDA5050Master::on_broker_reconnected() {}

// ============================================================================
// Master-broker connection state (Task #70)
// ============================================================================

VDA5050Master::BrokerStatusSnapshot VDA5050Master::get_broker_status() const
{
  std::lock_guard<std::mutex> lock(broker_status_mutex_);
  BrokerStatusSnapshot snap;
  snap.connected = broker_connected_;
  snap.last_disconnect_at = broker_last_disconnect_at_;
  snap.reconnect_count = broker_reconnect_count_;
  return snap;
}

void VDA5050Master::handle_broker_connection_lost(const std::string& cause)
{
  {
    std::lock_guard<std::mutex> lock(broker_status_mutex_);
    broker_connected_ = false;
    broker_last_disconnect_at_ = std::chrono::system_clock::now();
  }
  VDA5050_WARN(
    "[VDA5050Master] Broker connection lost: {}",
    cause.empty() ? "(no cause reported)" : cause.c_str());
  on_broker_disconnected();
}

void VDA5050Master::handle_broker_connected(const std::string& cause)
{
  std::uint64_t count = 0;
  {
    std::lock_guard<std::mutex> lock(broker_status_mutex_);
    broker_connected_ = true;
    broker_reconnect_count_ += 1;
    count = broker_reconnect_count_;
  }
  VDA5050_INFO(
    "[VDA5050Master] Broker connection established (count={}, cause={})", count,
    cause.empty() ? "initial" : cause.c_str());
  on_broker_reconnected();
}

}  // namespace vda5050_core::master
