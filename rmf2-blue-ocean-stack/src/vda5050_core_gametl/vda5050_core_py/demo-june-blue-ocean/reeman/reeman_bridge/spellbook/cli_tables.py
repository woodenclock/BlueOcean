"""Rich tables for interactive CLI selection prompts."""

from __future__ import annotations

from typing import Any, Sequence

from rich.console import Console
from rich.table import Table

_console = Console()


def _print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    justify: dict[str, str] | None = None,
) -> None:
    table = Table(show_header=True, header_style="bold")
    justify = justify or {}
    for h in headers:
        table.add_column(h, justify=justify.get(h, "left"))
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
    _console.print(table)


def print_maps_table(maps: list[dict[str, Any]]) -> None:
    rows = [
        (
            str(i),
            str(m.get("id", "")),
            str(m.get("map_uid", m.get("uid", ""))),
            str(m.get("map_name", "")),
        )
        for i, m in enumerate(maps)
    ]
    _print_table(
        ("key", "id", "uid", "name"),
        rows,
        justify={"key": "right", "id": "right"},
    )


def print_waypoints_table(wps: list[dict[str, Any]], *, limit: int | None = None) -> int:
    """Print waypoints table; return number of rows shown."""
    shown = wps if limit is None else wps[:limit]
    rows = [
        (
            str(i),
            str(w.get("kind", "")),
            str(w.get("name", "")),
            f"{w.get('x', 0.0):.4f}",
            f"{w.get('y', 0.0):.4f}",
            f"{w.get('ori', 0.0):.4f}",
        )
        for i, w in enumerate(shown)
    ]
    _print_table(
        ("key", "kind", "name", "x", "y", "ori"),
        rows,
        justify={"key": "right", "x": "right", "y": "right", "ori": "right"},
    )
    return len(shown)


def print_robots_table(robots: list[dict[str, str]] | list[tuple[str, dict[str, Any]]]) -> None:
    if robots and isinstance(robots[0], tuple):
        rows = [
            (str(i), name, str(cfg.get("ROBOT_IP", cfg.get("robot_ip", ""))))
            for i, (name, cfg) in enumerate(robots)  # type: ignore[misc]
        ]
    else:
        rows = [
            (str(i), str(r.get("name", "")), str(r.get("robot_ip", r.get("ROBOT_IP", ""))), str(r.get("timeout_ms", "")))
            for i, r in enumerate(robots)  # type: ignore[misc]
        ]
    _print_table(("key", "name", "robot_ip", "timeout_ms"), rows, justify={"key": "right", "timeout_ms": "right"})


def print_indexed_choices(items: Sequence[str], *, value_header: str = "value") -> None:
    rows = [(str(i), item) for i, item in enumerate(items)]
    _print_table(("key", value_header), rows, justify={"key": "right"})
