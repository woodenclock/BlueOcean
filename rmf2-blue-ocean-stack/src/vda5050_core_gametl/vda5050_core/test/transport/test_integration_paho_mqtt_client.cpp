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

#include <gmock/gmock.h>

#include <atomic>
#include <chrono>
#include <thread>

#include "vda5050_core/transport/mqtt_client_interface.hpp"
#include "vda5050_core/transport/paho_mqtt_client.hpp"

namespace {
// Poll until `pred()` returns true or `timeout` elapses. Returns true on
// success. Replaces hard-coded sleeps that are brittle under broker latency
// and CI load.
template <typename Predicate>
bool wait_for(Predicate pred, std::chrono::milliseconds timeout)
{
  using clock = std::chrono::steady_clock;
  const auto deadline = clock::now() + timeout;
  while (clock::now() < deadline)
  {
    if (pred()) return true;
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  return pred();
}
}  // namespace

TEST(PahoMqttClientTest, PublishSubscribe)
{
  std::string broker = "tcp://localhost:1883";
  std::string topic = "/test/integration";
  std::string payload = "hello";
  int qos = 0;

  std::atomic_int message_count{0};

  auto listener =
    vda5050_core::transport::PahoMqttClient::make_shared(broker, "listener");
  ASSERT_NO_THROW(listener->connect());
  ASSERT_TRUE(listener->connected());
  ASSERT_NO_THROW(listener->subscribe(
    topic,
    [&](const std::string& topic_, const std::string& payload_) {
      message_count++;
      ASSERT_EQ(topic, topic_);
      ASSERT_EQ(payload, payload_);
    },
    qos));

  auto talker =
    vda5050_core::transport::create_default_client_shared(broker, "talker");
  ASSERT_NO_THROW(talker->connect());
  ASSERT_NO_THROW(talker->publish(topic, payload, qos));

  EXPECT_TRUE(wait_for(
    [&] { return message_count.load() == 1; }, std::chrono::seconds(2)));
  EXPECT_EQ(message_count.load(), 1);

  ASSERT_NO_THROW(talker->disconnect());
  ASSERT_NO_THROW(listener->disconnect());
}

TEST(PahoMqttClientTest, UnsubscribeStopsMessages)
{
  std::string broker = "tcp://localhost:1883";
  std::string topic = "/test/integration/unsubscribe";
  std::string payload = "hello";
  int qos = 0;

  std::atomic_int message_count{0};

  auto listener = vda5050_core::transport::PahoMqttClient::make_unique(
    broker, "unsub_listener");
  ASSERT_NO_THROW(listener->connect());
  ASSERT_NO_THROW(listener->subscribe(
    topic,
    [&](const std::string& /*topic_*/, const std::string& /*payload_*/) {
      message_count++;
    },
    qos));

  auto talker = vda5050_core::transport::create_default_client_unique(
    broker, "unsub_talker");
  ASSERT_NO_THROW(talker->connect());

  // Publish first message and verify it is received
  ASSERT_NO_THROW(talker->publish(topic, payload, qos));
  EXPECT_TRUE(wait_for(
    [&] { return message_count.load() == 1; }, std::chrono::seconds(2)));
  ASSERT_EQ(message_count.load(), 1);

  // Unsubscribe from the topic. unsubscribe() waits for broker ack, so no
  // post-call sleep is required.
  ASSERT_NO_THROW(listener->unsubscribe(topic));

  // Publish second message after unsubscribe; allow plenty of time for any
  // stray delivery to land before asserting it didn't.
  ASSERT_NO_THROW(talker->publish(topic, payload, qos));
  std::this_thread::sleep_for(std::chrono::milliseconds(200));

  // Message count should still be 1 (no new messages received)
  ASSERT_EQ(message_count.load(), 1);

  ASSERT_NO_THROW(talker->disconnect());
  ASSERT_NO_THROW(listener->disconnect());
}

TEST(PahoMqttClient, LastWill)
{
  std::string broker = "tcp://localhost:1883";
  std::string topic = "/test/integration/unsubscribe";
  std::string payload = "hello";
  int qos = 0;

  auto client = vda5050_core::transport::PahoMqttClient::make_unique(
    broker, "last_will_client");
  ASSERT_NO_THROW(client->set_will(topic, payload, qos));
  ASSERT_NO_THROW(client->connect());
  ASSERT_TRUE(client->connected());

  ASSERT_EQ(client->connect_options().get_will_topic(), topic);
  ASSERT_EQ(client->connect_options().get_will_message()->to_string(), payload);

  ASSERT_NO_THROW(client->disconnect());
}

TEST(PahoMqttClientTest, FailedConnectionRemainsDisconnected)
{
  // Use an invalid broker endpoint to simulate connection failure
  std::string invalid_broker = "tcp://invalid.broker.address:1883";

  auto client = vda5050_core::transport::PahoMqttClient::make_shared(
    invalid_broker, "test_failed_connection");

  // Initial state should be disconnected
  ASSERT_FALSE(client->connected());

  // Attempt connection to invalid broker (should not throw)
  ASSERT_NO_THROW(client->connect());

  // connected() should return false after failed connection
  ASSERT_FALSE(client->connected());
}

TEST(PahoMqttClientTest, DisconnectReturnsPromptlyWithoutConnection)
{
  const std::string invalid_broker = "tcp://127.0.0.1:19999";

  auto client = vda5050_core::transport::PahoMqttClient::make_unique(
    invalid_broker, "prompt_disconnect_client");
  client->set_operation_timeout(std::chrono::milliseconds(500));

  const auto start = std::chrono::steady_clock::now();
  ASSERT_NO_THROW(client->connect());
  ASSERT_FALSE(client->connected());
  ASSERT_NO_THROW(client->disconnect());
  const auto elapsed = std::chrono::steady_clock::now() - start;

  EXPECT_LT(
    std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count(),
    2000)
    << "connect/disconnect to unreachable broker should be bounded by timeout";
}
