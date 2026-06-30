"""Smoke tests for the FMS-side master bindings — no broker required.

Verify the master surface imports, types construct, an Order can be built from
Python, the synchronous assign_order pre-flight runs, and VDA5050Master can be
subclassed to override callbacks. None of these call .connect() — onboarding
attempts an MQTT SUBSCRIBE that fails gracefully (logged) without a broker.
"""

import vda5050_core_py as vda


def test_master_surface():
    for name in (
        "VDA5050Master", "AGV", "Order", "Edge", "Header", "State",
        "NodeState", "EdgeState", "Error", "AssignmentResult",
        "AssignmentDecision", "ConnectionState", "OperatingMode",
        "ErrorLevel", "AGVState",
    ):
        assert hasattr(vda, name), name


def _make_master():
    mqtt = vda.create_default_mqtt_client("tcp://localhost:1883", "test_master")
    return vda.VDA5050Master.make(mqtt)


def test_onboard_and_get_agv():
    master = _make_master()
    assert master.is_connected() is False
    master.onboard_agv("Manufacturer", "S001")
    assert master.is_agv_onboarded("Manufacturer", "S001") is True
    assert ("Manufacturer", "S001") in master.get_onboarded_agvs()

    agv = master.get_agv("Manufacturer", "S001")
    assert agv is not None
    assert agv.get_agv_id() == "Manufacturer/S001"
    # Fresh, broker-less AGV: offline, unknown, no state yet.
    assert agv.get_connection_status() == vda.ConnectionState.OFFLINE
    assert agv.get_operational_state() == vda.AGVState.STATE_UNKNOWN
    assert agv.get_last_state() is None

    assert master.get_agv("nope", "nope") is None


def test_build_order_from_python():
    order = vda.Order()
    order.order_id = "demo"
    order.order_update_id = 0

    pos = vda.NodePosition()
    pos.x, pos.y, pos.map_id = -11.0, 1.2, "From Mapping 40"
    n0 = vda.Node()
    n0.node_id, n0.sequence_id, n0.released, n0.node_position = "n0", 0, True, pos
    n1 = vda.Node()
    n1.node_id, n1.sequence_id, n1.released = "n1", 2, True

    edge = vda.Edge()
    edge.edge_id, edge.sequence_id = "e0", 1
    edge.start_node_id, edge.end_node_id, edge.released = "n0", "n1", True

    order.nodes = [n0, n1]
    order.edges = [edge]

    assert len(order.nodes) == 2
    assert len(order.edges) == 1
    assert order.edges[0].start_node_id == "n0"


def test_assign_order_preflight_rejects_offline_agv():
    master = _make_master()
    master.onboard_agv("Manufacturer", "S001")

    order = vda.Order()
    order.order_id = "demo"
    n0 = vda.Node()
    n0.node_id, n0.sequence_id, n0.released = "n0", 0, True
    order.nodes = [n0]

    result = master.assign_order("Manufacturer", "S001", order)
    # AGV never reported ONLINE, so pre-flight must reject (not ASSIGNED).
    assert bool(result) is False
    assert result.decision == vda.AssignmentDecision.AGV_OFFLINE
    assert len(result.errors) >= 1


def test_subclass_overrides_callbacks():
    class RecordingMaster(vda.VDA5050Master):
        def __init__(self, mqtt):
            super().__init__(mqtt)
            self.reached = []

        def on_node_reached(self, agv_id, node_id):
            self.reached.append((agv_id, node_id))

    mqtt = vda.create_default_mqtt_client("tcp://localhost:1883", "sub_master")
    master = RecordingMaster(mqtt)
    master.onboard_agv("M", "2")
    assert ("M", "2") in master.get_onboarded_agvs()
    # We can't easily drive a real on_node_reached without a broker; this just
    # proves the trampoline subclass constructs and onboards without error.
    assert master.reached == []
