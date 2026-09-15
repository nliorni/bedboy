"""Shared Rich console and colour theme."""

from __future__ import annotations

import os

from rich.console import Console
from rich.theme import Theme

BEDBOY_THEME = Theme(
    {
        "bb.brand": "bold #c4b5fd",
        "bb.accent": "bold #93c5fd",
        "bb.ok": "bold #a7f3d0",
        "bb.warn": "bold yellow",
        "bb.err": "bold red",
        "bb.muted": "dim",
        "bb.path": "italic #93c5fd",
        "bb.gene": "bold #a7f3d0",
        "bb.num": "bold #c4b5fd",
    }
)


def make_console(no_color: bool = False, quiet: bool = False, stderr: bool = True) -> Console:
    """Build a Console honouring ``--no-color`` and the ``NO_COLOR`` env var."""
    disable = no_color or bool(os.environ.get("NO_COLOR"))
    return Console(
        theme=BEDBOY_THEME,
        no_color=disable,
        highlight=False,
        stderr=stderr,
        quiet=quiet,
    )
