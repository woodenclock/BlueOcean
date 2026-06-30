"""Track the live VDA5050 order off the broker so the adapter knows the full path.

The C++ Adapter subscribes to the order and drives it node by node, but it only
hands Python one node at a time via ``on_navigate`` — the order's full node list
(and therefore which node is the *final* one) is never exposed. The pass-through
optimisation needs that: a gentle intermediate waypoint may be coasted through,
but the final node must always be a precise stop.

This module independently subscribes to the same VDA5050 order topic on the
broker and caches the latest order's final node id, giving the adapter a cheap
``last_node_id()`` lookup. It is intentionally read-only and best-effort: if the
broker is unreachable or no order has arrived yet, ``last_node_id()`` returns
``None`` and the caller falls back to the safe default (full stop).
"""

from __future__ import annotations

import json
import sys
import threading
from urllib.parse import urlparse

import paho.mqtt.client as mqtt


def broker_host_port(broker: str, *, default_port: int = 1883) -> tuple[str, int]:
    """Parse ``tcp://host:1883`` / ``host:1883`` / ``host`` into (host, port)."""
    parsed = urlparse(broker if "://" in broker else f"tcp://{broker}")
    return (parsed.hostname or "localhost"), (parsed.port or default_port)


def order_topic(interface: str, protocol_version: str, manufacturer: str, serial: str) -> str:
    """VDA5050 order topic: ``{interface}/v{major}/{manufacturer}/{serial}/order``."""
    major = protocol_version.split(".", 1)[0]
    return f"{interface}/v{major}/{manufacturer}/{serial}/order"


def _final_node_id(order: dict) -> str | None:
    """The node id with the highest sequenceId in the order (its goal), or None."""
    nodes = order.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return None
    last = max(nodes, key=lambda n: n.get("sequenceId", -1) if isinstance(n, dict) else -1)
    node_id = last.get("nodeId") if isinstance(last, dict) else None
    return node_id if isinstance(node_id, str) else None


class OrderTracker:
    """Caches the final node id of the most recent VDA5050 order for one AGV."""

    def __init__(
        self,
        *,
        broker: str,
        interface: str,
        protocol_version: str,
        manufacturer: str,
        serial_number: str,
        client_id: str,
    ) -> None:
        self._host, self._port = broker_host_port(broker)
        self._topic = order_topic(interface, protocol_version, manufacturer, serial_number)
        self._lock = threading.Lock()
        self._last_node_id: str | None = None
        self._order_id: str | None = None

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=f"{client_id}_order_tracker"
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def start(self) -> None:
        """Connect and begin listening on a background thread (best-effort)."""
        try:
            self._client.connect(self._host, self._port)
        except OSError as exc:
            print(
                f"[order-tracker] connect to {self._host}:{self._port} failed: {exc}; "
                "last-node detection disabled (nodes default to full stop)",
                file=sys.stderr,
            )
            return
        self._client.loop_start()
        print(
            f"[order-tracker] listening on {self._topic} ({self._host}:{self._port})",
            file=sys.stderr,
        )

    def stop(self) -> None:
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except OSError:
            pass

    def last_node_id(self) -> str | None:
        """Final node id of the latest order, or ``None`` if no order seen yet."""
        with self._lock:
            return self._last_node_id

    # ── paho callbacks ─────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        client.subscribe(self._topic)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            order = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        if not isinstance(order, dict):
            return
        last = _final_node_id(order)
        if last is None:
            return
        with self._lock:
            self._order_id = order.get("orderId")
            self._last_node_id = last
