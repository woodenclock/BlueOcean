"""
Python bindings for vda5050_core: the AGV-side Adapter facade.
The C++ adapter owns the MQTT lifecycle, order graph execution, header IDs, and 1Hz state publishing. Python implements only the robot-side navigation callback and reports state back via NavigationManager.
"""
from __future__ import annotations
import typing
__all__: list[str] = ['AGV', 'AGVPosition', 'AGVState', 'Action', 'ActionParameter', 'ActionState', 'ActionStatus', 'Adapter', 'AssignmentDecision', 'AssignmentResult', 'BatteryState', 'BlockingType', 'ConnectionState', 'Edge', 'EdgeState', 'Error', 'ErrorLevel', 'Header', 'MqttClient', 'NavigationManager', 'Node', 'NodePosition', 'NodeState', 'OperatingMode', 'Order', 'ProtocolAdapter', 'State', 'VDA5050Master', 'create_default_mqtt_client']
class AGV:
    """
    Read-only handle to an onboarded AGV. Obtain via VDA5050Master.get_agv(); cannot be constructed directly.
    """
    def cancel_pending_orders(self) -> None:
        ...
    def get_agv_id(self) -> str:
        ...
    def get_connection_status(self) -> ConnectionState:
        ...
    def get_last_state(self) -> State | None:
        """
        Last received State message, or None if none received yet.
        """
    def get_manufacturer(self) -> str:
        ...
    def get_operational_state(self) -> AGVState:
        ...
    def get_pending_order_count(self) -> int:
        ...
    def get_serial_number(self) -> str:
        ...
    def is_connected(self) -> bool:
        ...
class AGVPosition:
    deviation_range: float | None
    localization_score: float | None
    map_description: str | None
    map_id: str
    position_initialized: bool
    theta: float
    x: float
    y: float
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class AGVState:
    """
    Members:
    
      STATE_UNKNOWN
    
      AVAILABLE
    
      UNAVAILABLE
    
      ERROR
    """
    AVAILABLE: typing.ClassVar[AGVState]  # value = <AGVState.AVAILABLE: 1>
    ERROR: typing.ClassVar[AGVState]  # value = <AGVState.ERROR: 3>
    STATE_UNKNOWN: typing.ClassVar[AGVState]  # value = <AGVState.STATE_UNKNOWN: 0>
    UNAVAILABLE: typing.ClassVar[AGVState]  # value = <AGVState.UNAVAILABLE: 2>
    __members__: typing.ClassVar[dict[str, AGVState]]  # value = {'STATE_UNKNOWN': <AGVState.STATE_UNKNOWN: 0>, 'AVAILABLE': <AGVState.AVAILABLE: 1>, 'UNAVAILABLE': <AGVState.UNAVAILABLE: 2>, 'ERROR': <AGVState.ERROR: 3>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Action:
    action_description: str | None
    action_id: str
    action_parameters: list[ActionParameter] | None
    action_type: str
    blocking_type: BlockingType
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class ActionParameter:
    key: str
    value: str
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class ActionState:
    action_description: str | None
    action_id: str
    action_status: ActionStatus
    action_type: str | None
    result_description: str | None
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class ActionStatus:
    """
    Members:
    
      WAITING
    
      INITIALIZING
    
      RUNNING
    
      PAUSED
    
      FINISHED
    
      FAILED
    """
    FAILED: typing.ClassVar[ActionStatus]  # value = <ActionStatus.FAILED: 5>
    FINISHED: typing.ClassVar[ActionStatus]  # value = <ActionStatus.FINISHED: 4>
    INITIALIZING: typing.ClassVar[ActionStatus]  # value = <ActionStatus.INITIALIZING: 1>
    PAUSED: typing.ClassVar[ActionStatus]  # value = <ActionStatus.PAUSED: 3>
    RUNNING: typing.ClassVar[ActionStatus]  # value = <ActionStatus.RUNNING: 2>
    WAITING: typing.ClassVar[ActionStatus]  # value = <ActionStatus.WAITING: 0>
    __members__: typing.ClassVar[dict[str, ActionStatus]]  # value = {'WAITING': <ActionStatus.WAITING: 0>, 'INITIALIZING': <ActionStatus.INITIALIZING: 1>, 'RUNNING': <ActionStatus.RUNNING: 2>, 'PAUSED': <ActionStatus.PAUSED: 3>, 'FINISHED': <ActionStatus.FINISHED: 4>, 'FAILED': <ActionStatus.FAILED: 5>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Adapter:
    """
    AGV-side facade. Wires a ProtocolAdapter into the execution framework, subscribes to Order, publishes State at 1Hz, and routes per-node navigation requests to the Python `on_navigate` callback.
    """
    @staticmethod
    def make(protocol_adapter: ProtocolAdapter) -> Adapter:
        """
        Construct an Adapter from a ProtocolAdapter. Start the spin loop with .start().
        """
    def navigation_manager(self) -> NavigationManager:
        """
        Return the NavigationManager for reporting node arrival and state.
        """
    def on_navigate(self, callback: typing.Callable[[Node], None]) -> None:
        """
        Register the per-node navigation callback. Signature: `Callable[[Node], None]`. Invoked on the C++ spin thread; long-running work (HTTP, polling) should be dispatched to a Python worker thread so the spin loop is not blocked.
        """
    def start(self) -> None:
        """
        Connect MQTT, subscribe to Order, publish ONLINE, and start the execution spin thread. Returns once the spin thread is running.
        """
    def stop(self) -> None:
        """
        Unsubscribe, stop the spin loop, publish OFFLINE, disconnect MQTT. Joins the spin thread; releases the GIL while waiting so in-flight Python callbacks can complete.
        """
class AssignmentDecision:
    """
    Members:
    
      ASSIGNED
    
      AGV_NOT_ONBOARDED
    
      AGV_OFFLINE
    
      AGV_NOT_READY
    
      AGV_MODE_NOT_AUTO
    
      AGV_POSITION_NOT_INITIALIZED
    
      AGV_NO_STATE_YET
    
      STITCH_REJECTED
    
      STITCH_QUEUED
    """
    AGV_MODE_NOT_AUTO: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.AGV_MODE_NOT_AUTO: 4>
    AGV_NOT_ONBOARDED: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.AGV_NOT_ONBOARDED: 1>
    AGV_NOT_READY: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.AGV_NOT_READY: 3>
    AGV_NO_STATE_YET: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.AGV_NO_STATE_YET: 6>
    AGV_OFFLINE: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.AGV_OFFLINE: 2>
    AGV_POSITION_NOT_INITIALIZED: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.AGV_POSITION_NOT_INITIALIZED: 5>
    ASSIGNED: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.ASSIGNED: 0>
    STITCH_QUEUED: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.STITCH_QUEUED: 8>
    STITCH_REJECTED: typing.ClassVar[AssignmentDecision]  # value = <AssignmentDecision.STITCH_REJECTED: 7>
    __members__: typing.ClassVar[dict[str, AssignmentDecision]]  # value = {'ASSIGNED': <AssignmentDecision.ASSIGNED: 0>, 'AGV_NOT_ONBOARDED': <AssignmentDecision.AGV_NOT_ONBOARDED: 1>, 'AGV_OFFLINE': <AssignmentDecision.AGV_OFFLINE: 2>, 'AGV_NOT_READY': <AssignmentDecision.AGV_NOT_READY: 3>, 'AGV_MODE_NOT_AUTO': <AssignmentDecision.AGV_MODE_NOT_AUTO: 4>, 'AGV_POSITION_NOT_INITIALIZED': <AssignmentDecision.AGV_POSITION_NOT_INITIALIZED: 5>, 'AGV_NO_STATE_YET': <AssignmentDecision.AGV_NO_STATE_YET: 6>, 'STITCH_REJECTED': <AssignmentDecision.STITCH_REJECTED: 7>, 'STITCH_QUEUED': <AssignmentDecision.STITCH_QUEUED: 8>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class AssignmentResult:
    def __bool__(self) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    @property
    def decision(self) -> AssignmentDecision:
        ...
    @property
    def errors(self) -> list[Error]:
        ...
class BatteryState:
    battery_charge: float
    battery_health: int | None
    battery_voltage: float | None
    charging: bool
    reach: int | None
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class BlockingType:
    """
    Members:
    
      NONE
    
      SOFT
    
      HARD
    """
    HARD: typing.ClassVar[BlockingType]  # value = <BlockingType.HARD: 2>
    NONE: typing.ClassVar[BlockingType]  # value = <BlockingType.NONE: 0>
    SOFT: typing.ClassVar[BlockingType]  # value = <BlockingType.SOFT: 1>
    __members__: typing.ClassVar[dict[str, BlockingType]]  # value = {'NONE': <BlockingType.NONE: 0>, 'SOFT': <BlockingType.SOFT: 1>, 'HARD': <BlockingType.HARD: 2>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class ConnectionState:
    """
    Members:
    
      ONLINE
    
      OFFLINE
    
      CONNECTIONBROKEN
    """
    CONNECTIONBROKEN: typing.ClassVar[ConnectionState]  # value = <ConnectionState.CONNECTIONBROKEN: 2>
    OFFLINE: typing.ClassVar[ConnectionState]  # value = <ConnectionState.OFFLINE: 1>
    ONLINE: typing.ClassVar[ConnectionState]  # value = <ConnectionState.ONLINE: 0>
    __members__: typing.ClassVar[dict[str, ConnectionState]]  # value = {'ONLINE': <ConnectionState.ONLINE: 0>, 'OFFLINE': <ConnectionState.OFFLINE: 1>, 'CONNECTIONBROKEN': <ConnectionState.CONNECTIONBROKEN: 2>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Edge:
    actions: list[Action]
    edge_id: str
    end_node_id: str
    max_speed: float | None
    released: bool
    sequence_id: int
    start_node_id: str
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class EdgeState:
    edge_id: str
    released: bool
    sequence_id: int
    def __init__(self) -> None:
        ...
class Error:
    error_description: str | None
    error_level: ErrorLevel
    error_type: str
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class ErrorLevel:
    """
    Members:
    
      WARNING
    
      FATAL
    """
    FATAL: typing.ClassVar[ErrorLevel]  # value = <ErrorLevel.FATAL: 1>
    WARNING: typing.ClassVar[ErrorLevel]  # value = <ErrorLevel.WARNING: 0>
    __members__: typing.ClassVar[dict[str, ErrorLevel]]  # value = {'WARNING': <ErrorLevel.WARNING: 0>, 'FATAL': <ErrorLevel.FATAL: 1>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Header:
    header_id: int
    manufacturer: str
    serial_number: str
    version: str
    def __init__(self) -> None:
        ...
class MqttClient:
    """
    Opaque MQTT client handle. Construct via create_default_mqtt_client.
    """
class NavigationManager:
    """
    Robot-side handle for reporting navigation completion and state. Obtained from Adapter.navigation_manager(); cannot be constructed directly.
    """
    def node_reached(self, node: Node) -> None:
        """
        Signal that the robot has reached `node`. Unblocks order execution so the next node in the order is dispatched.
        """
    def set_action_states(self, action_states: list[ActionState]) -> None:
        """
        Update the published State message's `actionStates` array.
        """
    def set_agv_position(self, position: AGVPosition) -> None:
        """
        Update the published State message's `agv_position`. Typically called at the robot's localization tick rate.
        """
    def set_battery_state(self, battery_state: BatteryState) -> None:
        """
        Update the published State message's `batteryState` fields.
        """
    def set_driving(self, driving: bool) -> None:
        """
        Update the published State message's `driving` flag.
        """
class Node:
    actions: list[Action]
    node_description: str | None
    node_id: str
    node_position: NodePosition | None
    released: bool
    sequence_id: int
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class NodePosition:
    allowed_deviation_theta: float | None
    allowed_deviation_x_y: float | None
    map_description: str | None
    map_id: str
    theta: float | None
    x: float
    y: float
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class NodeState:
    node_id: str
    node_position: NodePosition | None
    released: bool
    sequence_id: int
    def __init__(self) -> None:
        ...
class OperatingMode:
    """
    Members:
    
      AUTOMATIC
    
      SEMIAUTOMATIC
    
      MANUAL
    
      SERVICE
    
      TEACHIN
    """
    AUTOMATIC: typing.ClassVar[OperatingMode]  # value = <OperatingMode.AUTOMATIC: 0>
    MANUAL: typing.ClassVar[OperatingMode]  # value = <OperatingMode.MANUAL: 2>
    SEMIAUTOMATIC: typing.ClassVar[OperatingMode]  # value = <OperatingMode.SEMIAUTOMATIC: 1>
    SERVICE: typing.ClassVar[OperatingMode]  # value = <OperatingMode.SERVICE: 3>
    TEACHIN: typing.ClassVar[OperatingMode]  # value = <OperatingMode.TEACHIN: 4>
    __members__: typing.ClassVar[dict[str, OperatingMode]]  # value = {'AUTOMATIC': <OperatingMode.AUTOMATIC: 0>, 'SEMIAUTOMATIC': <OperatingMode.SEMIAUTOMATIC: 1>, 'MANUAL': <OperatingMode.MANUAL: 2>, 'SERVICE': <OperatingMode.SERVICE: 3>, 'TEACHIN': <OperatingMode.TEACHIN: 4>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: int) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: int) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Order:
    edges: list[Edge]
    header: Header
    nodes: list[Node]
    order_id: str
    order_update_id: int
    zone_set_id: str | None
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class ProtocolAdapter:
    @staticmethod
    def make(mqtt_client: MqttClient, interface: str, version: str, manufacturer: str, serial_number: str) -> ProtocolAdapter:
        """
        Create a ProtocolAdapter. `interface` is the VDA5050 interface name (usually "uagv"); `version` is the full protocol version (e.g. "2.1.0"); `manufacturer` and `serial_number` identify the AGV.
        """
    def connected(self) -> bool:
        ...
class State:
    action_states: list[ActionState]
    agv_position: AGVPosition | None
    battery_state: BatteryState
    distance_since_last_node: float | None
    driving: bool
    edge_states: list[EdgeState]
    errors: list[Error]
    last_node_id: str
    last_node_sequence_id: int
    node_states: list[NodeState]
    operating_mode: OperatingMode
    order_id: str
    order_update_id: int
    paused: bool | None
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
class VDA5050Master:
    """
    FMS-side facade managing multiple AGVs over one shared MQTT client. Subclass and override the on_* callbacks to react to AGV events; construct the subclass with a ProtocolAdapter MQTT client.
    """
    @staticmethod
    def make(mqtt_client: MqttClient) -> VDA5050Master:
        """
        Convenience factory for a master with default (no-op) callbacks.
        """
    def __init__(self, mqtt_client: MqttClient) -> None:
        """
        Construct a master from an MQTT client (see create_default_mqtt_client). Subclass this and call super().__init__(mqtt_client) to receive callbacks. The library uses make_shared internally (enable_shared_from_this).
        """
    def assign_order(self, manufacturer: str, serial_number: str, order: Order) -> AssignmentResult:
        """
        Synchronously check AGV readiness and assign the order. Returns an AssignmentResult; truthy iff ASSIGNED. Recommended FMS entry point.
        """
    def connect(self) -> None:
        """
        Connect the shared MQTT client to the broker.
        """
    def disconnect(self) -> None:
        """
        Disconnect the shared MQTT client.
        """
    def get_agv(self, manufacturer: str, serial_number: str) -> AGV:
        """
        Shared handle to an onboarded AGV, or None if not onboarded.
        """
    def get_onboarded_agvs(self) -> list[tuple[str, str]]:
        """
        List of (manufacturer, serial_number) tuples currently onboarded.
        """
    def is_agv_onboarded(self, manufacturer: str, serial_number: str) -> bool:
        """
        True iff the given AGV is currently onboarded.
        """
    def is_connected(self) -> bool:
        """
        True iff the master's MQTT client is connected.
        """
    def load_map_from_config(self, path: str) -> tuple[bool, list[str]]:
        """
        Load the master's topology map from a JSON config file.Returns (ok, [error_descriptions]).
        """
    def offboard_agv(self, manufacturer: str, serial_number: str) -> None:
        """
        Stop routing messages for an AGV and drop it from the allow list.
        """
    def onboard_agv(self, manufacturer: str, serial_number: str, max_queue_size: int = 10, drop_oldest: bool = True) -> None:
        """
        Register an AGV so its topics are subscribed and inbound messages are routed to it.
        """
    def publish_order(self, manufacturer: str, serial_number: str, order: Order) -> bool:
        """
        Lower-level queue+publish that bypasses the synchronous pre-flight of assign_order. Returns True if queued.
        """
def create_default_mqtt_client(broker_address: str, client_id: str) -> MqttClient:
    """
    Create a Paho-backed MQTT client. Pass the result to ProtocolAdapter.make().
    """
