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

/**
 * @file test_order_publisher.cpp
 * @brief Wire-up test for the OrderPublisher validator chain (Task #11).
 *
 * Confirms that a graph-invalid Order short-circuits the publisher chain
 * (returning ValidationResult with GraphValidationError) AND does NOT
 * reach MqttClientInterface::publish — i.e., the chain's short-circuit
 * fires before the MQTT publish.
 *
 * Uses a gmock MockMqttClient so the test runs without a real broker.
 * Mock pattern mirrors test/master/teardown_test.cpp.
 */

#include <gmock/gmock.h>

#include <functional>
#include <memory>
#include <string>

#include "vda5050_core/errors/error_codes.hpp"
#include "vda5050_core/execution/protocol_adapter.hpp"
#include "vda5050_core/master/map/map.hpp"
#include "vda5050_core/master/order/order_publisher.hpp"
#include "vda5050_core/master/validation/pre_send_validator.hpp"
#include "vda5050_core/transport/mqtt_client_interface.hpp"

namespace vda5050_core::master::test {

namespace {

class MockMqttClient : public vda5050_core::transport::MqttClientInterface
{
public:
  MOCK_METHOD(void, connect, (), (override));
  MOCK_METHOD(void, disconnect, (), (override));
  MOCK_METHOD(bool, connected, (), (override));
  MOCK_METHOD(
    void, publish, (const std::string&, const std::string&, int, bool),
    (override));
  MOCK_METHOD(
    void, subscribe,
    (const std::string&,
     std::function<void(const std::string&, const std::string&)>, int),
    (override));
  MOCK_METHOD(void, unsubscribe, (const std::string&), (override));
  MOCK_METHOD(
    void, set_will, (const std::string&, const std::string&, int, bool),
    (override));
};

// Build a PreSendContext that satisfies all #16 readiness checks so
// the chain reaches the graph step. Optional `last_node_id` parks the
// AGV on a specific node so traversability's "trivially reachable"
// check (state.last_node_id == first_node.node_id) passes — orders
// in these tests lack node_position so distance-based reachability
// would otherwise reject.
// Map matching every node/edge id used in the test fixtures
// (N0 -> E0 -> N1 -> E1 -> N2 plus a stitched-update extension
// N1 -> E2 -> N3). Required because the no-map gate (Task #39)
// hard-rejects when ctx.loaded_map is nullptr; the map-integrity
// sub-check then verifies node/edge ids exist in the loaded
// topology with matching endpoints.
std::shared_ptr<const Map> make_minimal_map()
{
  Map m;
  m.info.map_id = "test_map";
  m.info.map_version = "1.0";
  for (const auto& id : {"N0", "N1", "N2", "N3"})
  {
    MapNode n;
    n.node_id = id;
    m.node_index[id] = m.nodes.size();
    m.nodes.push_back(n);
  }
  struct EdgeSpec
  {
    const char* id;
    const char* from;
    const char* to;
  };
  for (const auto& spec :
       {EdgeSpec{"E0", "N0", "N1"}, EdgeSpec{"E1", "N1", "N2"},
        EdgeSpec{"E2", "N1", "N3"}, EdgeSpec{"E3", "N2", "N3"}})
  {
    MapEdge e;
    e.edge_id = spec.id;
    e.start_node_id = spec.from;
    e.end_node_id = spec.to;
    m.edge_index[e.edge_id] = m.edges.size();
    m.edges.push_back(e);
  }
  return std::make_shared<const Map>(std::move(m));
}

PreSendContext make_ready_context(const std::string& last_node_id = "")
{
  vda5050_core::types::State s;
  s.operating_mode = vda5050_core::types::OperatingMode::AUTOMATIC;
  vda5050_core::types::AGVPosition pos;
  pos.position_initialized = true;
  s.agv_position = pos;
  s.last_node_id = last_node_id;
  return PreSendContext{
    vda5050_core::types::ConnectionState::ONLINE,
    s,
    std::nullopt /* last_factsheet — graph step doesn't use it */,
    AGVState::AVAILABLE,
    std::nullopt /* active_order — set per-test for is_valid_update path */,
    make_minimal_map()};
}

// Build a schema-valid header so the schema gate passes and the chain
// reaches the graph step.
void fill_schema_valid_header(vda5050_core::types::Header& h)
{
  h.version = "2.0.0";
  h.manufacturer = "ACME";
  h.serial_number = "AGV001";
}

vda5050_core::types::Node mk_node(
  const std::string& id, uint32_t seq, bool released)
{
  vda5050_core::types::Node n;
  n.node_id = id;
  n.sequence_id = seq;
  n.released = released;
  return n;
}

vda5050_core::types::Edge mk_edge(
  const std::string& id, uint32_t seq, const std::string& from,
  const std::string& to, bool released)
{
  vda5050_core::types::Edge e;
  e.edge_id = id;
  e.sequence_id = seq;
  e.start_node_id = from;
  e.end_node_id = to;
  e.released = released;
  return e;
}

// Active V0 with released base [N0(0), N1(2)] + horizon [N2(4)] and
// connecting edges. Used as the "active_order" in PreSendContext for
// is_valid_update path tests.
vda5050_core::types::Order make_active_v0()
{
  vda5050_core::types::Order o;
  fill_schema_valid_header(o.header);
  o.order_id = "ORDER_A";
  o.order_update_id = 0;
  o.nodes = {
    mk_node("N0", 0, true), mk_node("N1", 2, true), mk_node("N2", 4, false)};
  o.edges = {
    mk_edge("E0", 1, "N0", "N1", true), mk_edge("E1", 3, "N1", "N2", false)};
  return o;
}

}  // namespace

// =============================================================================
// Defense-in-depth: each validator stage must short-circuit independently.
// These regression-guard tests prevent future refactors from accidentally
// dropping a stage from the chain.
// =============================================================================

TEST(OrderPublisherTest, MalformedOrderRejectedAtSchema)
{
  // Order with empty header.version → schema validator rejects.
  auto mock = std::make_shared<MockMqttClient>();
  auto adapter = vda5050_core::execution::ProtocolAdapter::make(
    mock, "rmf2", "v2", "ACME", "AGV001");
  vda5050_core::master::OrderPublisher publisher;

  vda5050_core::types::Order malformed;
  // header.version intentionally left empty
  malformed.order_id = "ORDER_A";
  malformed.order_update_id = 0;
  vda5050_core::types::Node n;
  n.node_id = "N0";
  n.sequence_id = 0;
  n.released = true;
  malformed.nodes = {n};

  EXPECT_CALL(
    *mock, publish(::testing::_, ::testing::_, ::testing::_, ::testing::_))
    .Times(0);

  auto ctx = make_ready_context();
  auto result = publisher.publish(*adapter, ctx, malformed);

  EXPECT_FALSE(static_cast<bool>(result));
  ASSERT_FALSE(result.errors.empty());
  bool found_schema_error = false;
  for (const auto& e : result.errors)
  {
    if (e.error_type == vda5050_core::errors::SchemaValidationError)
    {
      found_schema_error = true;
      break;
    }
  }
  EXPECT_TRUE(found_schema_error)
    << "expected SchemaValidationError; got first error type: "
    << result.errors.front().error_type;
}

TEST(OrderPublisherTest, NotReadyAGVRejectedAtPreSend)
{
  // PreSendContext with OFFLINE connection → PreSend validator rejects.
  auto mock = std::make_shared<MockMqttClient>();
  auto adapter = vda5050_core::execution::ProtocolAdapter::make(
    mock, "rmf2", "v2", "ACME", "AGV001");
  vda5050_core::master::OrderPublisher publisher;

  vda5050_core::types::Order order;
  fill_schema_valid_header(order.header);
  order.order_id = "ORDER_A";
  order.order_update_id = 0;
  vda5050_core::types::Node n;
  n.node_id = "N0";
  n.sequence_id = 0;
  n.released = true;
  order.nodes = {n};

  EXPECT_CALL(
    *mock, publish(::testing::_, ::testing::_, ::testing::_, ::testing::_))
    .Times(0);

  // Override the ready context's connection status to OFFLINE.
  auto ctx = make_ready_context();
  ctx.connection_status = vda5050_core::types::ConnectionState::OFFLINE;

  auto result = publisher.publish(*adapter, ctx, order);

  EXPECT_FALSE(static_cast<bool>(result));
  ASSERT_FALSE(result.errors.empty());
  bool found_pre_send_error = false;
  for (const auto& e : result.errors)
  {
    if (e.error_type == vda5050_core::errors::PreSendValidationError)
    {
      found_pre_send_error = true;
      break;
    }
  }
  EXPECT_TRUE(found_pre_send_error)
    << "expected PreSendValidationError; got first error type: "
    << result.errors.front().error_type;
}

TEST(OrderPublisherTest, GraphInvalidOrderShortCircuitsAndReportsGraphError)
{
  auto mock = std::make_shared<MockMqttClient>();
  auto adapter = vda5050_core::execution::ProtocolAdapter::make(
    mock, "rmf2", "v2", "ACME", "AGV001");
  vda5050_core::master::OrderPublisher publisher;

  // Build a graph-invalid Order: 2 nodes but 0 edges → violates
  // is_valid_graph's "edges = nodes - 1" rule.
  vda5050_core::types::Order bad_order;
  fill_schema_valid_header(bad_order.header);
  bad_order.order_id = "ORDER_BAD";
  bad_order.order_update_id = 0;

  vda5050_core::types::Node n0;
  n0.node_id = "N0";
  n0.sequence_id = 0;
  n0.released = true;
  vda5050_core::types::Node n1;
  n1.node_id = "N1";
  n1.sequence_id = 2;
  n1.released = true;
  bad_order.nodes = {n0, n1};
  // intentionally leave bad_order.edges empty

  // Mock must NOT be asked to publish — the chain short-circuits at
  // graph validation.
  EXPECT_CALL(
    *mock, publish(::testing::_, ::testing::_, ::testing::_, ::testing::_))
    .Times(0);

  auto ctx = make_ready_context();
  auto result = publisher.publish(*adapter, ctx, bad_order);

  EXPECT_FALSE(static_cast<bool>(result));
  ASSERT_FALSE(result.errors.empty());
  bool found_graph_error = false;
  for (const auto& e : result.errors)
  {
    if (e.error_type == vda5050_core::errors::GraphValidationError)
    {
      found_graph_error = true;
      break;
    }
  }
  EXPECT_TRUE(found_graph_error);
}

// =============================================================================
// #19: publisher chain branches on update vs new order.
// - No active_order, or different order_id → is_valid_graph(candidate)
// - Same order_id with active → combine_order(active, candidate) for
//   spec-strict structural validation (sparse seqs are expected).
// =============================================================================
namespace {

// Helper: spec-strict update U1 — first node is stitch anchor (V0's
// last released, N1@2), then extension at sparse seq (E2@5, N3@6).
// is_valid_graph rejects this standalone; combine_order accepts.
vda5050_core::types::Order make_stitched_update_v1()
{
  vda5050_core::types::Order o;
  fill_schema_valid_header(o.header);
  o.order_id = "ORDER_A";
  o.order_update_id = 1;
  o.nodes = {mk_node("N1", 2, true), mk_node("N3", 6, true)};
  o.edges = {mk_edge("E2", 5, "N1", "N3", true)};
  return o;
}

vda5050_core::master::PreSendContext make_ready_context_with_active(
  const vda5050_core::types::Order& active,
  const std::string& last_node_id = "N1")
{
  auto ctx = make_ready_context(last_node_id);
  ctx.active_order = active;
  return ctx;
}

}  // namespace

TEST(OrderPublisherTest, FreshOrderNoActiveTakesGraphPath)
{
  // No active → is_valid_graph branch runs on the full V0 graph (which is
  // a valid standalone graph). Publish succeeds.
  auto mock = std::make_shared<MockMqttClient>();
  auto adapter = vda5050_core::execution::ProtocolAdapter::make(
    mock, "rmf2", "v2", "ACME", "AGV001");
  vda5050_core::master::OrderPublisher publisher;
  auto v0 = make_active_v0();

  EXPECT_CALL(
    *mock, publish(::testing::_, ::testing::_, ::testing::_, ::testing::_))
    .Times(1);

  auto ctx = make_ready_context("N0");  // active_order = nullopt
  auto result = publisher.publish(*adapter, ctx, v0);
  EXPECT_TRUE(static_cast<bool>(result)) << "errors=" << result.errors.size();
}

TEST(OrderPublisherTest, StitchedUpdateValidatedViaCombineOrder)
{
  // active_order set + same order_id → combine_order branch. Candidate
  // has sparse seqs ([N1@2, E2@5, N3@6]) which would fail is_valid_graph
  // standalone, but combine_order accepts because the stitch node matches
  // V0's last released (N1@2) and the extension is past the horizon.
  auto mock = std::make_shared<MockMqttClient>();
  auto adapter = vda5050_core::execution::ProtocolAdapter::make(
    mock, "rmf2", "v2", "ACME", "AGV001");
  vda5050_core::master::OrderPublisher publisher;

  EXPECT_CALL(
    *mock, publish(::testing::_, ::testing::_, ::testing::_, ::testing::_))
    .Times(1);

  auto ctx = make_ready_context_with_active(make_active_v0());
  auto u1 = make_stitched_update_v1();
  auto result = publisher.publish(*adapter, ctx, u1);
  EXPECT_TRUE(static_cast<bool>(result)) << "errors=" << result.errors.size();
}

TEST(OrderPublisherTest, StitchedUpdateBackwardUpdateIdRejected)
{
  // combine_order rejects update_update_id <= active.order_update_id.
  auto mock = std::make_shared<MockMqttClient>();
  auto adapter = vda5050_core::execution::ProtocolAdapter::make(
    mock, "rmf2", "v2", "ACME", "AGV001");
  vda5050_core::master::OrderPublisher publisher;
  EXPECT_CALL(
    *mock, publish(::testing::_, ::testing::_, ::testing::_, ::testing::_))
    .Times(0);

  auto active = make_active_v0();
  active.order_update_id = 5;
  auto ctx = make_ready_context_with_active(active);

  auto candidate = make_stitched_update_v1();
  candidate.order_update_id = 3;  // backward
  auto result = publisher.publish(*adapter, ctx, candidate);
  EXPECT_FALSE(static_cast<bool>(result));
}

TEST(OrderPublisherTest, StitchedUpdateStitchNodeMismatchRejected)
{
  // combine_order rejects when candidate.nodes[0] differs from active's
  // last released base node (stitch identity rule).
  auto mock = std::make_shared<MockMqttClient>();
  auto adapter = vda5050_core::execution::ProtocolAdapter::make(
    mock, "rmf2", "v2", "ACME", "AGV001");
  vda5050_core::master::OrderPublisher publisher;
  EXPECT_CALL(
    *mock, publish(::testing::_, ::testing::_, ::testing::_, ::testing::_))
    .Times(0);

  auto ctx = make_ready_context_with_active(make_active_v0());
  auto candidate = make_stitched_update_v1();
  candidate.nodes.front().node_id = "N1_RENAMED";  // stitch mismatch

  auto result = publisher.publish(*adapter, ctx, candidate);
  EXPECT_FALSE(static_cast<bool>(result));
}

TEST(OrderPublisherTest, DifferentOrderIdTakesGraphPath)
{
  // active.order_id != candidate.order_id → graph path (treated as new
  // order). The candidate is structurally valid as a standalone graph.
  auto mock = std::make_shared<MockMqttClient>();
  auto adapter = vda5050_core::execution::ProtocolAdapter::make(
    mock, "rmf2", "v2", "ACME", "AGV001");
  vda5050_core::master::OrderPublisher publisher;
  EXPECT_CALL(
    *mock, publish(::testing::_, ::testing::_, ::testing::_, ::testing::_))
    .Times(1);

  auto active = make_active_v0();
  active.order_id = "OTHER_ORDER";  // different id → graph path
  // AGV parked on N0 — traversability reachability check passes for V0.
  auto ctx = make_ready_context_with_active(active, "N0");

  // For graph path, candidate must be a valid standalone graph (V0 is).
  auto v0_as_new = make_active_v0();
  auto result = publisher.publish(*adapter, ctx, v0_as_new);
  EXPECT_TRUE(static_cast<bool>(result)) << "errors=" << result.errors.size();
}

}  // namespace vda5050_core::master::test
