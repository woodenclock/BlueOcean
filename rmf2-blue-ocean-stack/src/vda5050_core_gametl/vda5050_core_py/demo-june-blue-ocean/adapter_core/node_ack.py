"""Shared node-acknowledgement helper for an out-of-band cancelled move."""

from __future__ import annotations

import sys

import vda5050_core_py as vda


def ack_cancelled_node(node: vda.Node, nav: vda.NavigationManager) -> None:
    """Ack a node whose move was cancelled out-of-band (Stop & reset / MAPF supersede).

    The C++ order executor is suspended waiting for THIS node's ack
    (adapter.cpp ``suspend_for<NodeAckUpdate>``, 300 s); without it the order
    never finishes, the AGV keeps reporting node_states, and the master sees
    ``order_active=true`` forever — a zombie that makes it stitch-queue (and
    refuse) every subsequent MAPF order. So we ack the node to drain the order
    and clear order_active.

    SPEC NOTE: this reports the node "reached" when the robot did NOT arrive
    (VDA5050 §6 — node acknowledgement implies arrival). We knowingly violate
    that for the demo so Stop & reset always leaves the robot truly idle and
    Apply (MAPF) works again immediately. (A spec-correct fix is the §6.10.2
    cancelOrder instant action, which the adapter does not yet implement — see
    adapter.cpp on_cancel.)
    """
    print(
        f"  cancelled → ack node {node.node_id} to clear the order "
        "(no zombie; spec-violating, demo-only)",
        file=sys.stderr,
    )
    nav.node_reached(node)
