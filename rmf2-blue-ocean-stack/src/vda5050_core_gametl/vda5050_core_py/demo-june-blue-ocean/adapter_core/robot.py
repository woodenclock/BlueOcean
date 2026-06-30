"""The per-robot hook surface the shared runner drives.

A concrete adapter (autoxing, reeman) subclasses :class:`RobotAdapter`, fills in
``config`` / ``endpoint_env``, and overrides the hooks that differ per robot.
The runner (:func:`adapter_core.runner.run`) owns the identical lifecycle around
them — identity bootstrap, the MQTT/adapter wiring, and ``run_until_signal``.
"""

from __future__ import annotations

import argparse

import vda5050_core_py as vda


class RobotAdapter:
    """Base adapter; subclasses set ``config``/``endpoint_env`` and override hooks."""

    #: CONFIG dict (see :func:`adapter_core.config.base_config`).
    config: dict
    #: Env var the bridge reads for the robot host (AUTOXING_BASE_URL / REEMAN_ROBOT_IP).
    endpoint_env: str = "ROBOT_BASE_URL"

    def __init__(self) -> None:
        self.disable_state_log = False

    # ── lifecycle hooks ─────────────────────────────────────────────────────

    def prepare(self, me: dict, args: argparse.Namespace) -> None:
        """One-time setup after identity is resolved: export the endpoint, ensure
        the onboard map, load any transform/calibration. Default is a no-op."""

    def config_extra_lines(self) -> list[str]:
        """Extra lines for the startup config block (e.g. transform). Default none."""
        return []

    def on_start(self, nav: vda.NavigationManager) -> None:
        """Start any side channels (e.g. the order tracker) before the adapter runs."""

    def seed_initial_pose(self, nav: vda.NavigationManager) -> None:
        """Poll the robot once and seed the published State's agvPosition."""

    def start_pose_stream(self, nav: vda.NavigationManager) -> None:
        """Start the daemon that keeps agvPosition live while idle. Default none."""

    def drive_to_node(self, node: vda.Node, nav: vda.NavigationManager) -> None:
        """Blocking navigate + poll for one node; calls ``nav.node_reached`` when done."""
        raise NotImplementedError
