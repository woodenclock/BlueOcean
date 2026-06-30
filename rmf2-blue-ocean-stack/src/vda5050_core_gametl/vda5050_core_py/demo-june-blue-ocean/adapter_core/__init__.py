"""Robot-agnostic core for the VDA5050 demo adapter clients.

The two demo adapters (autoxing, reeman) share everything except how a single
node is driven and how pose is read from the robot. That shared machinery lives
here — master REST lookups, identity bootstrap, the MQTT/adapter run loop — and
each robot package supplies a :class:`~adapter_core.robot.RobotAdapter`.
"""

from __future__ import annotations

from adapter_core.runner import run

__all__ = ["run"]
