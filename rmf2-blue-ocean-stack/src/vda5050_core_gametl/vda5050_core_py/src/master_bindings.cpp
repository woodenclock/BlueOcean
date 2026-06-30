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
 */

#include "master_bindings.hpp"

#include <pybind11/stl.h>

#include <memory>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <vda5050_core/master/agv.hpp>
#include <vda5050_core/master/assignment_result.hpp>
#include <vda5050_core/master/master.hpp>
#include <vda5050_core/types/instant_actions.hpp>
#include <vda5050_core/master/actions/instant_action_assignment_result.hpp>
#include <vda5050_core/transport/mqtt_client_interface.hpp>
#include <vda5050_core/types/connection_state.hpp>
#include <vda5050_core/types/edge.hpp>
#include <vda5050_core/types/edge_state.hpp>
#include <vda5050_core/types/error.hpp>
#include <vda5050_core/types/error_level.hpp>
#include <vda5050_core/types/header.hpp>
#include <vda5050_core/types/node_state.hpp>
#include <vda5050_core/types/operating_mode.hpp>
#include <vda5050_core/types/order.hpp>
#include <vda5050_core/types/state.hpp>

namespace py = pybind11;
using namespace vda5050_core;

namespace vda5050_core_py {

namespace {

// Trampoline so Python subclasses of VDA5050Master can override the event
// callbacks. Only the callbacks whose argument types are already bound are
// surfaced here (State, Error, OperatingMode, strings, bools); on_connection /
// on_factsheet / on_visualization / on_loads_changed / on_broker_* are left
// for a later pass once their message types are bound.
//
// PYBIND11_OVERRIDE acquires the GIL before dispatching, which is required:
// these fire on the MQTT transport / heartbeat threads, not a Python thread.
class PyVDA5050Master : public master::VDA5050Master
{
public:
  using master::VDA5050Master::VDA5050Master;

  void on_state(const std::string& agv_id, const types::State& state) override
  {
    PYBIND11_OVERRIDE(void, master::VDA5050Master, on_state, agv_id, state);
  }
  void on_node_reached(
    const std::string& agv_id, const std::string& node_id) override
  {
    PYBIND11_OVERRIDE(
      void, master::VDA5050Master, on_node_reached, agv_id, node_id);
  }
  void on_errors_appeared(
    const std::string& agv_id,
    const std::vector<types::Error>& new_errors) override
  {
    PYBIND11_OVERRIDE(
      void, master::VDA5050Master, on_errors_appeared, agv_id, new_errors);
  }
  void on_errors_resolved(
    const std::string& agv_id,
    const std::vector<types::Error>& resolved_errors) override
  {
    PYBIND11_OVERRIDE(
      void, master::VDA5050Master, on_errors_resolved, agv_id, resolved_errors);
  }
  void on_new_base_requested(const std::string& agv_id) override
  {
    PYBIND11_OVERRIDE(
      void, master::VDA5050Master, on_new_base_requested, agv_id);
  }
  void on_mode_changed(
    const std::string& agv_id, types::OperatingMode new_mode,
    types::OperatingMode prev_mode) override
  {
    PYBIND11_OVERRIDE(
      void, master::VDA5050Master, on_mode_changed, agv_id, new_mode,
      prev_mode);
  }
  void on_paused(const std::string& agv_id, bool paused) override
  {
    PYBIND11_OVERRIDE(void, master::VDA5050Master, on_paused, agv_id, paused);
  }
  void on_driving(const std::string& agv_id, bool driving) override
  {
    PYBIND11_OVERRIDE(void, master::VDA5050Master, on_driving, agv_id, driving);
  }
  void on_connect(const std::string& agv_id) override
  {
    PYBIND11_OVERRIDE(void, master::VDA5050Master, on_connect, agv_id);
  }
  void on_offline(const std::string& agv_id) override
  {
    PYBIND11_OVERRIDE(void, master::VDA5050Master, on_offline, agv_id);
  }
  void on_connection_broken(const std::string& agv_id) override
  {
    PYBIND11_OVERRIDE(
      void, master::VDA5050Master, on_connection_broken, agv_id);
  }
  void on_state_timeout(const std::string& agv_id) override
  {
    PYBIND11_OVERRIDE(void, master::VDA5050Master, on_state_timeout, agv_id);
  }
  void on_state_resumed(const std::string& agv_id) override
  {
    PYBIND11_OVERRIDE(void, master::VDA5050Master, on_state_resumed, agv_id);
  }
};

}  // namespace

void register_master_bindings(py::module_& m)
{
  // ===== Enums =====
  py::enum_<types::ConnectionState>(m, "ConnectionState")
    .value("ONLINE", types::ConnectionState::ONLINE)
    .value("OFFLINE", types::ConnectionState::OFFLINE)
    .value("CONNECTIONBROKEN", types::ConnectionState::CONNECTIONBROKEN);

  py::enum_<types::OperatingMode>(m, "OperatingMode")
    .value("AUTOMATIC", types::OperatingMode::AUTOMATIC)
    .value("SEMIAUTOMATIC", types::OperatingMode::SEMIAUTOMATIC)
    .value("MANUAL", types::OperatingMode::MANUAL)
    .value("SERVICE", types::OperatingMode::SERVICE)
    .value("TEACHIN", types::OperatingMode::TEACHIN);

  py::enum_<types::ErrorLevel>(m, "ErrorLevel")
    .value("WARNING", types::ErrorLevel::WARNING)
    .value("FATAL", types::ErrorLevel::FATAL);

  py::enum_<master::AGVState>(m, "AGVState")
    .value("STATE_UNKNOWN", master::AGVState::STATE_UNKNOWN)
    .value("AVAILABLE", master::AGVState::AVAILABLE)
    .value("UNAVAILABLE", master::AGVState::UNAVAILABLE)
    .value("ERROR", master::AGVState::ERROR);

  py::enum_<master::AssignmentDecision>(m, "AssignmentDecision")
    .value("ASSIGNED", master::AssignmentDecision::ASSIGNED)
    .value("AGV_NOT_ONBOARDED", master::AssignmentDecision::AGV_NOT_ONBOARDED)
    .value("AGV_OFFLINE", master::AssignmentDecision::AGV_OFFLINE)
    .value("AGV_NOT_READY", master::AssignmentDecision::AGV_NOT_READY)
    .value("AGV_MODE_NOT_AUTO", master::AssignmentDecision::AGV_MODE_NOT_AUTO)
    .value(
      "AGV_POSITION_NOT_INITIALIZED",
      master::AssignmentDecision::AGV_POSITION_NOT_INITIALIZED)
    .value("AGV_NO_STATE_YET", master::AssignmentDecision::AGV_NO_STATE_YET)
    .value("STITCH_REJECTED", master::AssignmentDecision::STITCH_REJECTED)
    .value("STITCH_QUEUED", master::AssignmentDecision::STITCH_QUEUED);

  // ===== Order-side types (Node / NodePosition / Action already bound) =====
  py::class_<types::Header>(m, "Header")
    .def(py::init<>())
    .def_readwrite("header_id", &types::Header::header_id)
    .def_readwrite("version", &types::Header::version)
    .def_readwrite("manufacturer", &types::Header::manufacturer)
    .def_readwrite("serial_number", &types::Header::serial_number);

  py::class_<types::Edge>(m, "Edge")
    .def(py::init<>())
    .def_readwrite("edge_id", &types::Edge::edge_id)
    .def_readwrite("sequence_id", &types::Edge::sequence_id)
    .def_readwrite("start_node_id", &types::Edge::start_node_id)
    .def_readwrite("end_node_id", &types::Edge::end_node_id)
    .def_readwrite("released", &types::Edge::released)
    .def_readwrite("actions", &types::Edge::actions)
    .def_readwrite("max_speed", &types::Edge::max_speed)
    .def("__repr__", [](const types::Edge& e) {
      std::ostringstream s;
      s << "Edge(edge_id='" << e.edge_id << "', sequence_id=" << e.sequence_id
        << ", " << e.start_node_id << "->" << e.end_node_id << ")";
      return s.str();
    });

  py::class_<types::Order>(m, "Order")
    .def(py::init<>())
    .def_readwrite("header", &types::Order::header)
    .def_readwrite("order_id", &types::Order::order_id)
    .def_readwrite("order_update_id", &types::Order::order_update_id)
    .def_readwrite("nodes", &types::Order::nodes)
    .def_readwrite("edges", &types::Order::edges)
    .def_readwrite("zone_set_id", &types::Order::zone_set_id)
    .def("__repr__", [](const types::Order& o) {
      std::ostringstream s;
      s << "Order(order_id='" << o.order_id
        << "', order_update_id=" << o.order_update_id
        << ", nodes=" << o.nodes.size() << ", edges=" << o.edges.size() << ")";
      return s.str();
    });

  py::class_<types::InstantActions>(m, "InstantActions")
    .def(py::init<>())
    .def_readwrite("header", &types::InstantActions::header)
    .def_readwrite("actions", &types::InstantActions::actions)
    .def("__repr__", [](const types::InstantActions& ia) {
      std::ostringstream s;
      s << "InstantActions(actions=" << ia.actions.size() << ")";
      return s.str();
    });

  // ===== State-side types (AGVPosition / BatteryState / ActionState bound) ==
  py::class_<types::NodeState>(m, "NodeState")
    .def(py::init<>())
    .def_readwrite("node_id", &types::NodeState::node_id)
    .def_readwrite("sequence_id", &types::NodeState::sequence_id)
    .def_readwrite("released", &types::NodeState::released)
    .def_readwrite("node_position", &types::NodeState::node_position);

  py::class_<types::EdgeState>(m, "EdgeState")
    .def(py::init<>())
    .def_readwrite("edge_id", &types::EdgeState::edge_id)
    .def_readwrite("sequence_id", &types::EdgeState::sequence_id)
    .def_readwrite("released", &types::EdgeState::released);

  py::class_<types::Error>(m, "Error")
    .def(py::init<>())
    .def_readwrite("error_type", &types::Error::error_type)
    .def_readwrite("error_description", &types::Error::error_description)
    .def_readwrite("error_level", &types::Error::error_level)
    .def("__repr__", [](const types::Error& e) {
      return "Error(error_type='" + e.error_type + "')";
    });

  py::class_<types::State>(m, "State")
    .def(py::init<>())
    .def_readwrite("order_id", &types::State::order_id)
    .def_readwrite("order_update_id", &types::State::order_update_id)
    .def_readwrite("last_node_id", &types::State::last_node_id)
    .def_readwrite(
      "last_node_sequence_id", &types::State::last_node_sequence_id)
    .def_readwrite("node_states", &types::State::node_states)
    .def_readwrite("edge_states", &types::State::edge_states)
    .def_readwrite("agv_position", &types::State::agv_position)
    .def_readwrite("driving", &types::State::driving)
    .def_readwrite("paused", &types::State::paused)
    .def_readwrite(
      "distance_since_last_node", &types::State::distance_since_last_node)
    .def_readwrite("action_states", &types::State::action_states)
    .def_readwrite("battery_state", &types::State::battery_state)
    .def_readwrite("operating_mode", &types::State::operating_mode)
    .def_readwrite("errors", &types::State::errors)
    .def("__repr__", [](const types::State& s) {
      std::ostringstream out;
      out << "State(order_id='" << s.order_id << "', last_node_id='"
          << s.last_node_id << "', driving=" << (s.driving ? "True" : "False")
          << ", node_states=" << s.node_states.size() << ")";
      return out.str();
    });

  // ===== AssignmentResult =====
  py::class_<master::AssignmentResult>(m, "AssignmentResult")
    .def_readonly("decision", &master::AssignmentResult::decision)
    .def_readonly("errors", &master::AssignmentResult::errors)
    .def(
      "__bool__",
      [](const master::AssignmentResult& r) { return static_cast<bool>(r); })
    .def("__repr__", [](const master::AssignmentResult& r) {
      std::ostringstream s;
      s << "AssignmentResult(assigned="
        << (static_cast<bool>(r) ? "True" : "False")
        << ", errors=" << r.errors.size() << ")";
      return s.str();
    });

  py::enum_<master::InstantActionDecision>(m, "InstantActionDecision")
    .value("ASSIGNED", master::InstantActionDecision::ASSIGNED)
    .value("AGV_NOT_ONBOARDED", master::InstantActionDecision::AGV_NOT_ONBOARDED)
    .value("AGV_OFFLINE", master::InstantActionDecision::AGV_OFFLINE)
    .value("DUPLICATE_ACTION_ID", master::InstantActionDecision::DUPLICATE_ACTION_ID)
    .value("AGV_QUEUE_FULL", master::InstantActionDecision::AGV_QUEUE_FULL)
    .value("HARD_ACTION_BLOCKED", master::InstantActionDecision::HARD_ACTION_BLOCKED)
    .value("ACTION_BLOCKED_BY_DRIVING", master::InstantActionDecision::ACTION_BLOCKED_BY_DRIVING)
    .value("AGV_MODE_NOT_AUTO_FOR_ACTION", master::InstantActionDecision::AGV_MODE_NOT_AUTO_FOR_ACTION);

  py::class_<master::InstantActionAssignmentResult>(m, "InstantActionAssignmentResult")
    .def_readonly("decision", &master::InstantActionAssignmentResult::decision)
    .def_readonly("errors", &master::InstantActionAssignmentResult::errors)
    .def("__bool__", [](const master::InstantActionAssignmentResult& r) {
      return static_cast<bool>(r);
    })
    .def("__repr__", [](const master::InstantActionAssignmentResult& r) {
      std::ostringstream s;
      s << "InstantActionAssignmentResult(assigned="
        << (static_cast<bool>(r) ? "True" : "False")
        << ", errors=" << r.errors.size() << ")";
      return s.str();
    });

  // ===== AGV (read-only handle obtained from VDA5050Master.get_agv) =====
  py::class_<master::AGV, std::shared_ptr<master::AGV>>(
    m, "AGV",
    "Read-only handle to an onboarded AGV. Obtain via "
    "VDA5050Master.get_agv(); cannot be constructed directly.")
    .def("get_manufacturer", &master::AGV::get_manufacturer)
    .def("get_serial_number", &master::AGV::get_serial_number)
    .def("get_agv_id", &master::AGV::get_agv_id)
    .def("is_connected", &master::AGV::is_connected)
    .def("get_connection_status", &master::AGV::get_connection_status)
    .def("get_operational_state", &master::AGV::get_operational_state)
    .def(
      "get_last_state", &master::AGV::get_last_state,
      "Last received State message, or None if none received yet.")
    .def("get_pending_order_count", &master::AGV::get_pending_order_count)
    .def(
      "cancel_pending_orders", &master::AGV::cancel_pending_orders,
      py::call_guard<py::gil_scoped_release>());

  // ===== VDA5050Master =====
  py::class_<
    master::VDA5050Master, PyVDA5050Master,
    std::shared_ptr<master::VDA5050Master>>(
    m, "VDA5050Master",
    "FMS-side facade managing multiple AGVs over one shared MQTT client. "
    "Subclass and override the on_* callbacks to react to AGV events; "
    "construct the subclass with a ProtocolAdapter MQTT client.")
    .def(
      py::init<std::shared_ptr<transport::MqttClientInterface>>(),
      py::arg("mqtt_client"),
      "Construct a master from an MQTT client (see "
      "create_default_mqtt_client). "
      "Subclass this and call super().__init__(mqtt_client) to receive "
      "callbacks. The library uses make_shared internally "
      "(enable_shared_from_this).")
    .def_static(
      "make",
      [](std::shared_ptr<transport::MqttClientInterface> mqtt_client) {
        return std::shared_ptr<master::VDA5050Master>(
          std::make_shared<PyVDA5050Master>(std::move(mqtt_client)));
      },
      py::arg("mqtt_client"),
      "Convenience factory for a master with default (no-op) callbacks.")
    .def(
      "connect", &master::VDA5050Master::connect,
      py::call_guard<py::gil_scoped_release>(),
      "Connect the shared MQTT client to the broker.")
    .def(
      "disconnect", &master::VDA5050Master::disconnect,
      py::call_guard<py::gil_scoped_release>(),
      "Disconnect the shared MQTT client.")
    .def(
      "is_connected", &master::VDA5050Master::is_connected,
      py::call_guard<py::gil_scoped_release>(),
      "True iff the master's MQTT client is connected.")
    .def(
      "onboard_agv", &master::VDA5050Master::onboard_agv,
      py::arg("manufacturer"), py::arg("serial_number"),
      py::arg("max_queue_size") = 10, py::arg("drop_oldest") = true,
      py::call_guard<py::gil_scoped_release>(),
      "Register an AGV so its topics are subscribed and inbound messages "
      "are routed to it.")
    .def(
      "offboard_agv", &master::VDA5050Master::offboard_agv,
      py::arg("manufacturer"), py::arg("serial_number"),
      py::call_guard<py::gil_scoped_release>(),
      "Stop routing messages for an AGV and drop it from the allow list.")
    .def(
      "is_agv_onboarded", &master::VDA5050Master::is_agv_onboarded,
      py::arg("manufacturer"), py::arg("serial_number"),
      "True iff the given AGV is currently onboarded.")
    .def(
      "get_onboarded_agvs", &master::VDA5050Master::get_onboarded_agvs,
      "List of (manufacturer, serial_number) tuples currently onboarded.")
    .def(
      "get_agv", &master::VDA5050Master::get_agv, py::arg("manufacturer"),
      py::arg("serial_number"),
      "Shared handle to an onboarded AGV, or None if not onboarded.")
    .def(
      "assign_order", &master::VDA5050Master::assign_order,
      py::arg("manufacturer"), py::arg("serial_number"), py::arg("order"),
      py::call_guard<py::gil_scoped_release>(),
      "Synchronously check AGV readiness and assign the order. Returns an "
      "AssignmentResult; truthy iff ASSIGNED. Recommended FMS entry point.")
    .def(
      "publish_order", &master::VDA5050Master::publish_order,
      py::arg("manufacturer"), py::arg("serial_number"), py::arg("order"),
      py::call_guard<py::gil_scoped_release>(),
      "Lower-level queue+publish that bypasses the synchronous pre-flight of "
      "assign_order. Returns True if queued.")
    .def(
      "publish_instant_actions",
      &master::VDA5050Master::publish_instant_actions,
      py::arg("manufacturer"), py::arg("serial_number"), py::arg("actions"),
      py::call_guard<py::gil_scoped_release>(),
      "Lower-level: queue and publish instantActions without pre-flight checks. "
      "Returns True if queued.")
    .def(
      "assign_instant_actions",
      &master::VDA5050Master::assign_instant_actions,
      py::arg("manufacturer"), py::arg("serial_number"), py::arg("actions"),
      py::call_guard<py::gil_scoped_release>(),
      "Pre-flight checked instantActions dispatch. Returns InstantActionAssignmentResult; "
      "truthy iff ASSIGNED.")
    .def(
      "load_map_from_config",
      [](master::VDA5050Master& self, const std::string& path) {
        auto result = self.load_map_from_config(path);
        std::vector<std::string> errs;
        for (const auto& e : result.errors) errs.push_back(e.description);
        return std::make_pair(static_cast<bool>(result), errs);
      },
      py::arg("path"), py::call_guard<py::gil_scoped_release>(),
      "Load the master's topology map from a JSON config file."
      "Returns (ok, [error_descriptions]).");
}

}  // namespace vda5050_core_py
