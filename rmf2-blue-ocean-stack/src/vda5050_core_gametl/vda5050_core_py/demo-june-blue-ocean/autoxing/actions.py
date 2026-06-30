"""HARD-blocking node actions (jackUp / jackDown) reported via action_states."""

from __future__ import annotations

import sys

import vda5050_core_py as vda

from autoxing.bridge import jack_down, jack_up


def execute_node_actions(node: vda.Node, nav: vda.NavigationManager) -> None:
    """Execute jackUp/jackDown node actions and report via action_states.

    Called before node_reached so the VDA5050 State reflects the action while it
    is in progress. ``jack_up``/``jack_down`` block until the jack physically
    settles. Only jackUp and jackDown are handled; other action_types are skipped
    with a warning.
    """
    if not node.actions:
        return

    active: list[vda.ActionState] = []

    for action in node.actions:
        atype = action.action_type
        if atype not in ("jackUp", "jackDown"):
            print(f"  [action] unsupported action_type={atype!r}, skipping", file=sys.stderr)
            continue

        as_run = vda.ActionState()
        as_run.action_id = action.action_id
        as_run.action_type = atype
        as_run.action_status = vda.ActionStatus.RUNNING
        active = [s for s in active if s.action_id != action.action_id]
        active.append(as_run)
        nav.set_action_states(active)
        print(f"  [action] {atype} RUNNING (id={action.action_id})", file=sys.stderr)

        try:
            result = jack_up() if atype == "jackUp" else jack_down()
            success = result is not None
        except Exception as exc:  # noqa: BLE001 — action failure must not crash nav
            print(f"  [action] {atype} error: {exc}", file=sys.stderr)
            success = False

        as_done = vda.ActionState()
        as_done.action_id = action.action_id
        as_done.action_type = atype
        as_done.action_status = (
            vda.ActionStatus.FINISHED if success else vda.ActionStatus.FAILED
        )
        active = [s for s in active if s.action_id != action.action_id]
        active.append(as_done)
        nav.set_action_states(active)
        print(f"  [action] {atype} {'FINISHED' if success else 'FAILED'}", file=sys.stderr)
