from __future__ import annotations

from typing import Iterable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


console = Console()


def banner(title: str, subtitle: str | None = None, border_style: str = "cyan") -> None:
    body = Text(title, style="bold cyan")
    if subtitle:
        body.append(f"\n{subtitle}", style="dim cyan")
    console.print(
        Panel(
            body,
            box=box.SQUARE,
            border_style=border_style,
            padding=(1, 2),
            expand=False,
        )
    )


def fit_panel(
    content: str,
    title: str | None = None,
    border_style: str = "cyan",
) -> None:
    console.print(
        Panel.fit(
            content,
            title=title,
            border_style=border_style,
            box=box.SQUARE,
        )
    )


def ok(message: str) -> None:
    console.print(f"[green]✓[/green] {message}")


def info(message: str) -> None:
    console.print(f"[cyan]i[/cyan] {message}")


def warn(message: str) -> None:
    console.print(f"[yellow]![/yellow] {message}")


def error(message: str) -> None:
    console.print(f"[red]✗[/red] {message}")


def kv_table(title: str, rows: Iterable[tuple[str, object]]) -> None:
    table = Table(
        title=title,
        box=box.SQUARE,
        show_lines=True,
        expand=False,
        border_style="cyan",
    )
    table.add_column("项目", style="cyan", min_width=14, overflow="fold")
    table.add_column("内容", min_width=36, overflow="fold")

    for key, value in rows:
        table.add_row(str(key), str(value))

    console.print(table)


def simple_table(
    title: str,
    columns: list[tuple[str, dict]],
    rows: list[list[str]],
) -> None:
    table = Table(
        title=title,
        box=box.SQUARE,
        show_lines=True,
        expand=False,
        border_style="cyan",
    )

    for name, options in columns:
        table.add_column(name, **options)

    for row in rows:
        table.add_row(*row)

    console.print(table)


def path_list(title: str, paths: Iterable[str]) -> None:
    rows = [
        [str(index), path]
        for index, path in enumerate(paths, start=1)
    ]

    simple_table(
        title,
        [
            ("No.", {"style": "magenta", "width": 4, "justify": "right"}),
            ("路径", {"style": "cyan", "min_width": 42, "overflow": "fold"}),
        ],
        rows,
    )


def print_json_text(text: str) -> None:
    console.print_json(text)
