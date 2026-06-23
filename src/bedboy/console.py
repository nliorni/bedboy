"""Shared Rich console and colour theme."""
from __future__ import annotations

import os

from rich.console import Console
from rich.theme import Theme

BEDBOY_THEME = Theme(
    {
        "bb.brand": "bold red",
        "bb.accent": "bold cyan",
        "bb.ok": "bold green",
        "bb.warn": "bold yellow",
        "bb.err": "bold red",
        "bb.muted": "dim",
        "bb.path": "italic cyan",
        "bb.gene": "bold green",
        "bb.num": "bold magenta",
    }
)


def make_console(no_color: bool = False, quiet: bool = False, stderr: bool = False) -> Console:
    """Build a Console honouring ``--no-color`` and the ``NO_COLOR`` env var."""
    disable = no_color or bool(os.environ.get("NO_COLOR"))
    return Console(
        theme=BEDBOY_THEME,
        no_color=disable,
        highlight=False,
        stderr=stderr,
        quiet=quiet,
    )
