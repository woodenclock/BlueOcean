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

#include "vda5050_core/master/order/order_publisher.hpp"

#include <cstdint>

#include "vda5050_core/master/order/order_lifecycle_manager.hpp"
#include "vda5050_core/master/standard_names.hpp"
#include "vda5050_core/master/validation/pre_send_validator.hpp"
#include "vda5050_core/master/validation/schema_validator.hpp"
#include "vda5050_core/master/validation/traversability_validator.hpp"
#include "vda5050_core/order_utils/order_graph_validator.hpp"

namespace vda5050_core::master {

vda5050_core::order_utils::ValidationResult OrderPublisher::publish(
  vda5050_core::execution::ProtocolAdapter& adapter, const PreSendContext& ctx,
  const vda5050_core::types::Order& order)
{
  // Validator chain: schema → PreSend → structural → traversability →
  // publish. Each link short-circuits on failure.
  auto schema_result = validate_order_schema(order);
  if (!schema_result)
  {
    return schema_result;
  }

  auto pre_send_result = validate_pre_send(ctx);
  if (!pre_send_result)
  {
    return pre_send_result;
  }

  // Structural validation branches on update vs new order.
  //
  // For a fresh order (no active, or different order_id): `is_valid_graph`
  // validates the full graph standalone — consecutive sequence_ids,
  // alternating node/edge pattern, base/horizon split.
  //
  // For an UPDATE (active present + same order_id): the candidate has
  // sparse sequence_ids by spec (it only contains the stitch node + new
  // nodes/edges; base seqs are absent because the spec forbids
  // retransmitting them). So `is_valid_graph` cannot be applied to the
  // candidate alone — we use `combine_order` instead, which validates
  // stitch identity, base immutability, monotonic order_update_id,
  // released-node preservation, etc., against the active order. The
  // merged result is discarded — we publish the candidate as-sent.
  //
  // (Future: vda5050_core's `is_valid_update` could subsume this once
  // its inner `is_valid_graph(next)` call is fixed for sparse seqs;
  // see follow-up #E3.)
  if (
    ctx.active_order.has_value() &&
    ctx.active_order->order_id == order.order_id)
  {
    const uint32_t last_seq =
      ctx.last_state.has_value() ? ctx.last_state->last_node_sequence_id : 0;
    auto combine_res = combine_order(*ctx.active_order, order, last_seq);
    if (!combine_res)
    {
      vda5050_core::order_utils::ValidationResult res;
      res.errors = std::move(combine_res.errors);
      return res;
    }
  }
  else
  {
    auto graph_result = vda5050_core::order_utils::is_valid_graph(order);
    if (!graph_result) return graph_result;
  }

  auto traversability_result = validate_traversability(ctx, order);
  if (!traversability_result)
  {
    return traversability_result;
  }

  adapter.publish<vda5050_core::types::Order>(
    order, static_cast<int>(OrderQos));

  return vda5050_core::order_utils::ValidationResult{};  // success
}

}  // namespace vda5050_core::master
