#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any

import websockets

from api_client import parse_json_file, print_json, request_api
from credentials import CONSTANTS as ROBOT
from credentials import timeout_seconds
from ws_helper import ws_uri_from_robot_ip

DEFAULT_CREATOR = "autoxing_spellbook_cli"

MOVE_TYPES = (
    "standard",
    "charge",
    "return_to_elevator_waiting_point",
    "enter_elevator",
    "leave_elevator",
    "along_given_route",
    "align_with_rack",
    "to_unload_point",
    "follow_target",
)


def base_url_for_docs() -> str:
    from credentials import CONSTANTS as ROBOT

    return f"{ROBOT.PREFIX}{ROBOT.ROBOT_IP}".rstrip("/")


def navigate(
    target_x: float | None = None,
    target_y: float | None = None,
    target_ori: float | None = None,
    *,
    move_type: str = "standard",
    creator: str | None = None,
    target_accuracy: float | None = None,
    target_z: float | None = None,
    route_coordinates: str | None = None,
    detour_tolerance: float | None = None,
    use_target_zone: bool | None = None,
    charge_retry_count: int | None = None,
    rack_area_id: str | None = None,
    inplace_rotate: bool | None = None,
    rack_layer: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict | None:
    """POST /chassis/moves — full MoveRequest per openapi.yaml.

    When ``target_ori`` is null, ``target_ori`` is omitted from the payload.
    Null is not treated as 0.
    """
    payload: dict[str, Any] = {
        "creator": creator or DEFAULT_CREATOR,
        "type": move_type,
    }
    if target_x is not None:
        payload["target_x"] = float(target_x)
    if target_y is not None:
        payload["target_y"] = float(target_y)
    if target_ori is not None:
        payload["target_ori"] = float(target_ori)
    if target_z is not None:
        payload["target_z"] = float(target_z)
    if target_accuracy is not None:
        payload["target_accuracy"] = float(target_accuracy)
    if route_coordinates is not None:
        payload["route_coordinates"] = route_coordinates
    if detour_tolerance is not None:
        payload["detour_tolerance"] = float(detour_tolerance)
    if use_target_zone is not None:
        payload["use_target_zone"] = bool(use_target_zone)
    if charge_retry_count is not None:
        payload["charge_retry_count"] = int(charge_retry_count)
    if rack_area_id is not None:
        payload["rack_area_id"] = rack_area_id
    props: dict[str, Any] = {}
    if inplace_rotate is not None:
        props["inplace_rotate"] = bool(inplace_rotate)
    if rack_layer is not None:
        props["rack_layer"] = int(rack_layer)
    if props:
        payload["properties"] = props
    if extra:
        for k, v in extra.items():
            if k in payload and isinstance(payload[k], dict) and isinstance(v, dict):
                payload[k] = {**payload[k], **v}
            else:
                payload[k] = v

    data = request_api("POST", "/chassis/moves", json_body=payload)
    return data if isinstance(data, dict) else None


_TERMINAL_MOVE_STATES = frozenset({"succeeded", "failed", "cancelled"})
_PLANNING_TOPIC = "/planning_state"


def planning_move_state(msg: Any) -> str | None:
    if not isinstance(msg, dict) or msg.get("topic") != _PLANNING_TOPIC:
        return None
    state = msg.get("move_state")
    return state if isinstance(state, str) else None


def should_cancel_on_interrupt(last_move_state: str | None) -> bool:
    """Cancel when interrupted unless the planner already reported ``succeeded``."""
    return last_move_state != "succeeded"


@dataclass
class _MoveWatchState:
    last_move_state: str | None = None
    terminal_state: str | None = None


def _print_planning_status(state: str) -> None:
    if state == "succeeded":
        hint = "done"
    elif state == "moving":
        hint = "moving — Ctrl+C to cancel"
    elif state in ("failed", "cancelled"):
        hint = state
    else:
        hint = f"{state} — Ctrl+C to cancel"
    sys.stderr.write(f"\rmoving.... ({hint})   ")
    sys.stderr.flush()


def _handle_planning_message(state: _MoveWatchState, data: object) -> None:
    move_state = planning_move_state(data)
    if move_state is None:
        return
    state.last_move_state = move_state
    _print_planning_status(move_state)
    if move_state in _TERMINAL_MOVE_STATES:
        state.terminal_state = move_state


async def _monitor_move_planning_async(state: _MoveWatchState) -> None:
    """Stream ``/planning_state`` until terminal state or KeyboardInterrupt."""
    want = {_PLANNING_TOPIC}
    ot = timeout_seconds()
    uri = ws_uri_from_robot_ip(ROBOT.ROBOT_IP)

    async with websockets.connect(uri, open_timeout=ot) as ws:
        await ws.send(json.dumps({"enable_topic": _PLANNING_TOPIC}))
        print("moving....", file=sys.stderr, flush=True)
        while state.terminal_state is None:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            topic = data.get("topic")
            if isinstance(topic, str) and topic in want:
                _handle_planning_message(state, data)


def monitor_move_after_dispatch() -> None:
    """Watch ``/planning_state``; cancel on Ctrl+C unless move already ``succeeded``."""
    from cancel_move import cancel_move_robust

    watch = _MoveWatchState()
    interrupted = False
    try:
        asyncio.run(_monitor_move_planning_async(watch))
    except KeyboardInterrupt:
        interrupted = True
    finally:
        sys.stderr.write("\n")
        sys.stderr.flush()
        if watch.terminal_state == "succeeded":
            print("Move finished: succeeded", file=sys.stderr)
        elif watch.terminal_state:
            print(f"Move finished: {watch.terminal_state}", file=sys.stderr)
        elif interrupted and should_cancel_on_interrupt(watch.last_move_state):
            print(
                "Interrupt — sending cancel (PATCH /chassis/moves/current)…",
                file=sys.stderr,
                flush=True,
            )
            cancel_move_robust()


def _merge_extra_json(s: str | None) -> dict[str, Any] | None:
    if not s:
        return None
    obj = json.loads(s)
    if not isinstance(obj, dict):
        raise ValueError("--json-extra must be a JSON object")
    return obj


if __name__ == "__main__":
    from get_waypoints import get_waypoints

    parser = argparse.ArgumentParser(
        description="POST /chassis/moves — navigation / charge / route / elevator / rack move types.",
    )
    parser.add_argument(
        "rest",
        nargs="*",
        help="Either three numbers X Y ORI (radians), or one waypoint name (standard only)",
    )
    parser.add_argument(
        "--type",
        choices=MOVE_TYPES,
        default="standard",
        help="Move type (OpenAPI MoveType)",
    )
    parser.add_argument("--target-x", type=float)
    parser.add_argument("--target-y", type=float)
    parser.add_argument("--target-ori", type=float)
    parser.add_argument("--target-z", type=float)
    parser.add_argument("--target-accuracy", type=float)
    parser.add_argument("--route", "--route-coordinates", dest="route_coordinates", help="CSV x1,y1,x2,y2,...")
    parser.add_argument("--detour-tolerance", type=float)
    parser.add_argument("--use-target-zone", action="store_true")
    parser.add_argument("--no-target-zone", action="store_true", dest="no_target_zone")
    parser.add_argument("--charge-retry-count", type=int)
    parser.add_argument("--rack-area-id")
    parser.add_argument("--inplace-rotate", action="store_true")
    parser.add_argument("--no-inplace-rotate", action="store_true", dest="no_inplace_rotate")
    parser.add_argument("--rack-layer", type=int)
    parser.add_argument("--creator", default=None)
    parser.add_argument("--json-extra", help='merge JSON object, e.g.\'{{"rack_area_id":"a"}}\'')
    parser.add_argument("--body-file", help="full MoveRequest JSON (overrides other flags)")
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="exit immediately after POST (no /planning_state watch or interrupt cancel)",
    )
    args = parser.parse_args()

    extra: dict[str, Any] | None = None
    if args.json_extra:
        extra = _merge_extra_json(args.json_extra)

    use_zone: bool | None = None
    if args.use_target_zone:
        use_zone = True
    elif args.no_target_zone:
        use_zone = False

    ir: bool | None = None
    if args.inplace_rotate:
        ir = True
    elif args.no_inplace_rotate:
        ir = False

    if args.body_file:
        payload = parse_json_file(args.body_file)
        if not isinstance(payload, dict):
            print("body-file must contain a JSON object", file=sys.stderr)
            sys.exit(1)
        data = request_api("POST", "/chassis/moves", json_body=payload)
        out = data if isinstance(data, dict) else None
        if out is not None:
            print_json(out)
            if not args.no_monitor:
                monitor_move_after_dispatch()
        sys.exit(0 if out is not None else 1)

    ax = args.target_x
    ay = args.target_y
    ao = args.target_ori

    if args.rest:
        if len(args.rest) == 3:
            try:
                ax, ay, ao = float(args.rest[0]), float(args.rest[1]), float(args.rest[2])
            except ValueError:
                print("Three rest args must be numeric X Y ORI.", file=sys.stderr)
                sys.exit(1)
        elif len(args.rest) == 1 and args.type == "standard":
            target_name = args.rest[0]
            wps = get_waypoints() or []
            hit = False
            for w in wps:
                if w.get("name") == target_name:
                    ax, ay, ao = w["x"], w["y"], w["ori"]
                    hit = True
                    break
            if not hit:
                print(f"Waypoint {target_name!r} not found in overlays.", file=sys.stderr)
                sys.exit(1)
        else:
            print("Provide three numbers X Y ORI, one waypoint name, or use --target-x/--target-y.", file=sys.stderr)
            sys.exit(1)
    elif args.type == "standard" and ax is None and ay is None:
        from cli_tables import print_waypoints_table

        wps = get_waypoints() or []
        if not wps:
            print(
                "No overlay points — provide: navigate X Y ORI\n"
                "(or upload map with landmarks/chargers in overlays.)",
                file=sys.stderr,
            )
            sys.exit(1)
        print_waypoints_table(wps)
        sel = input("Index: ").strip()
        if not sel.isdigit() or int(sel) >= len(wps):
            sys.exit(1)
        p = wps[int(sel)]
        ax, ay, ao = p["x"], p["y"], p["ori"]

    out = navigate(
        ax,
        ay,
        ao,
        move_type=args.type,
        creator=args.creator,
        target_accuracy=args.target_accuracy,
        target_z=args.target_z,
        route_coordinates=args.route_coordinates,
        detour_tolerance=args.detour_tolerance,
        use_target_zone=use_zone,
        charge_retry_count=args.charge_retry_count,
        rack_area_id=args.rack_area_id,
        inplace_rotate=ir,
        rack_layer=args.rack_layer,
        extra=extra,
    )
    if out is not None:
        print_json(out)
        if not args.no_monitor:
            monitor_move_after_dispatch()
    else:
        sys.exit(1)
