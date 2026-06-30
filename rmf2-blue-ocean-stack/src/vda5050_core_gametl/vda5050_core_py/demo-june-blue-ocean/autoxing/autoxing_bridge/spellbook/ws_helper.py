"""Minimal WebSocket helper for AXBot `/ws/v2/topics` (subscribe + read)."""

from __future__ import annotations

import asyncio
import json
import signal
import sys
from collections.abc import Callable
from typing import Any

import websockets

from credentials import CONSTANTS as ROBOT
from credentials import timeout_seconds

from api_client import request_api


def supports_enable_topic_list(*, print_errors: bool = False, timeout: float | None = None) -> bool:
    """True if ``GET /device/info`` reports ``caps.supportsEnableTopicList``."""
    t = timeout_seconds() if timeout is None else timeout
    info = request_api("GET", "/device/info", print_errors=print_errors, timeout=t)
    if not isinstance(info, dict):
        return False
    caps = info.get("caps") or {}
    return bool(caps.get("supportsEnableTopicList"))


def ws_uri_from_robot_ip(robot_ip: str) -> str:
    """Build ``ws://host:port/ws/v2/topics`` from ``ROBOT_IP`` (host:port, no scheme)."""
    host_port = robot_ip.strip()
    for prefix in ("http://", "https://", "ws://", "wss://"):
        if host_port.startswith(prefix):
            host_port = host_port[len(prefix) :]
            break
    host_port = host_port.rstrip("/")
    return f"ws://{host_port}/ws/v2/topics"


async def _ws_collect_first(
    robot_ip: str,
    topics: list[str],
    *,
    timeout: float,
    use_topic_list: bool | None = None,
) -> dict[str, Any]:
    uri = ws_uri_from_robot_ip(robot_ip)
    want = set(topics)
    seen: dict[str, Any] = {}

    if use_topic_list is None:
        use_topic_list = supports_enable_topic_list() if len(topics) > 1 else True

    async with websockets.connect(uri, open_timeout=timeout) as ws:
        if len(topics) == 1:
            await ws.send(json.dumps({"enable_topic": topics[0]}))
        elif use_topic_list:
            await ws.send(json.dumps({"enable_topic": topics}))
        else:
            for t in topics:
                await ws.send(json.dumps({"enable_topic": t}))

        deadline = asyncio.get_event_loop().time() + timeout
        while want - set(seen.keys()):
            remaining = max(0.1, deadline - asyncio.get_event_loop().time())
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            topic = data.get("topic")
            if isinstance(topic, str) and topic in want and topic not in seen:
                seen[topic] = data

    return seen


async def _ws_send_disable(robot_ip: str, topic: str, *, open_timeout: float | None = None) -> None:
    ot = timeout_seconds() if open_timeout is None else open_timeout
    uri = ws_uri_from_robot_ip(robot_ip)
    async with websockets.connect(uri, open_timeout=ot) as ws:
        await ws.send(json.dumps({"disable_topic": topic}))


def ws_disable_topic(robot_ip: str, topic: str) -> None:
    """Send ``disable_topic`` once (e.g. after long subscribe sessions)."""
    asyncio.run(_ws_send_disable(robot_ip, topic))


def ws_get_topics(
    robot_ip: str,
    topics: list[str],
    *,
    timeout: float | None = None,
    use_topic_list: bool | None = None,
) -> dict[str, Any]:
    """Subscribe and return the first JSON message received per requested topic."""
    t = timeout_seconds() if timeout is None else timeout
    return asyncio.run(_ws_collect_first(robot_ip, topics, timeout=t, use_topic_list=use_topic_list))


async def _ws_stream_topic(
    robot_ip: str,
    topic: str,
    *,
    duration_sec: float,
    max_messages: int | None = None,
) -> list[Any]:
    uri = ws_uri_from_robot_ip(robot_ip)
    out: list[Any] = []
    t0 = asyncio.get_event_loop().time()
    payload = {"enable_topic": topic}

    async with websockets.connect(uri, open_timeout=timeout_seconds()) as ws:
        await ws.send(json.dumps(payload))
        while asyncio.get_event_loop().time() - t0 < duration_sec:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if data.get("topic") == topic:
                out.append(data)
                if max_messages is not None and len(out) >= max_messages:
                    break
    return out


def ws_poll_topic(
    robot_ip: str,
    topic: str,
    *,
    duration_sec: float = 15.0,
    max_messages: int | None = None,
) -> list[Any]:
    """Collect messages for ``topic`` over ``duration_sec`` (non-blocking interval 0.5s)."""
    return asyncio.run(
        _ws_stream_topic(
            robot_ip,
            topic,
            duration_sec=duration_sec,
            max_messages=max_messages,
        )
    )


async def _watch_stdin_eof(stop: asyncio.Event) -> None:
    """Stop streaming when stdin closes (Ctrl+D on an empty line in a TTY)."""
    if not sys.stdin.isatty():
        return
    loop = asyncio.get_running_loop()
    fd = sys.stdin.fileno()

    def _poll_stdin() -> None:
        if stop.is_set():
            return
        try:
            chunk = sys.stdin.read(1)
        except (OSError, ValueError):
            stop.set()
            return
        if chunk == "":
            stop.set()

    loop.add_reader(fd, _poll_stdin)
    try:
        await stop.wait()
    finally:
        try:
            loop.remove_reader(fd)
        except Exception:
            pass


async def _ws_stream_topics(
    robot_ip: str,
    topics: list[str],
    *,
    max_messages: int | None,
    use_topic_list: bool | None,
    stop_event: asyncio.Event,
    on_message: Callable[[Any], None],
    open_timeout: float | None = None,
) -> int:
    uri = ws_uri_from_robot_ip(robot_ip)
    want = set(topics)
    count = 0
    ot = timeout_seconds() if open_timeout is None else open_timeout

    if use_topic_list is None:
        use_topic_list = supports_enable_topic_list() if len(topics) > 1 else True

    async with websockets.connect(uri, open_timeout=ot) as ws:
        if len(topics) == 1:
            await ws.send(json.dumps({"enable_topic": topics[0]}))
        elif use_topic_list:
            await ws.send(json.dumps({"enable_topic": topics}))
        else:
            for t in topics:
                await ws.send(json.dumps({"enable_topic": t}))

        while not stop_event.is_set():
            if max_messages is not None and count >= max_messages:
                break
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
                on_message(data)
                count += 1
                if max_messages is not None and count >= max_messages:
                    break

    return count


async def _run_ws_stream_topics(
    robot_ip: str,
    topics: list[str],
    *,
    max_messages: int | None,
    use_topic_list: bool | None,
    on_message: Callable[[Any], None],
    open_timeout: float | None = None,
) -> int:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    watcher: asyncio.Task[None] | None = None
    sigint_installed = False
    ot = timeout_seconds() if open_timeout is None else open_timeout

    if max_messages is None:
        watcher = asyncio.create_task(_watch_stdin_eof(stop))
        try:
            loop.add_signal_handler(signal.SIGINT, stop.set)
            sigint_installed = True
        except (NotImplementedError, RuntimeError):
            pass

    try:
        return await _ws_stream_topics(
            robot_ip,
            topics,
            max_messages=max_messages,
            use_topic_list=use_topic_list,
            stop_event=stop,
            on_message=on_message,
            open_timeout=ot,
        )
    finally:
        stop.set()
        if sigint_installed:
            try:
                loop.remove_signal_handler(signal.SIGINT)
            except Exception:
                pass
        if watcher is not None:
            try:
                await watcher
            except asyncio.CancelledError:
                pass


def ws_stream_topics(
    robot_ip: str,
    topics: list[str],
    *,
    max_messages: int | None = None,
    use_topic_list: bool | None = None,
    on_message: Callable[[Any], None] | None = None,
    open_timeout: float | None = None,
) -> int:
    """
    Stream messages for ``topics`` until ``max_messages``, Ctrl+D (stdin EOF), or KeyboardInterrupt.

    When ``max_messages`` is set, exits as soon as that many payloads are delivered (no stdin watch).

    Returns the number of messages delivered to ``on_message``.
    """
    delivered = 0

    def _default_on_message(data: Any) -> None:
        nonlocal delivered
        delivered += 1

    handler = on_message or _default_on_message
    return asyncio.run(
        _run_ws_stream_topics(
            robot_ip,
            topics,
            max_messages=max_messages,
            use_topic_list=use_topic_list,
            on_message=handler,
            open_timeout=open_timeout,
        )
    )
