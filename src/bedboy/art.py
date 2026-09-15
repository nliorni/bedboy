"""ASCII art, banners and the BedBoy mascot."""

from __future__ import annotations

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

# Block-letter wordmark: BEDBOY
WORDMARK = r"""
██████╗ ███████╗██████╗ ██████╗  ██████╗ ██╗   ██╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔═══██╗╚██╗ ██╔╝
██████╔╝█████╗  ██║  ██║██████╔╝██║   ██║ ╚████╔╝
██╔══██╗██╔══╝  ██║  ██║██╔══██╗██║   ██║  ╚██╔╝
██████╔╝███████╗██████╔╝██████╔╝╚██████╔╝   ██║
╚═════╝ ╚══════╝╚═════╝ ╚═════╝  ╚═════╝    ╚═╝
"""

# A boy tucked into a quilt: the BED is both the mascot and the file format.
BED_BOY = r"""
                           z
                       z
                   z
       .-------------------------------.
       |  .-------.                    |
       | (  - . -  )___                |
       |  '-------'    \_______________|
       |  |   *     .     *     .     *|
       |  |      B E D  B O Y          |
       |  | .     *     .     *     .  |
       |__|____________________________|
       |__|                         |__|
"""

TAGLINE = "gene names, without leaving bed"


def _gradient(text: str, colors: list[str]) -> Text:
    """Apply a vertical colour gradient (one colour per line)."""
    out = Text()
    lines = text.strip("\n").splitlines()
    for i, line in enumerate(lines):
        c = colors[min(i * len(colors) // max(len(lines), 1), len(colors) - 1)]
        out.append(line + "\n", style=c)
    return out


def mascot(version: str = "") -> Group:
    """A sleeping boy, a starry quilt and a moonlit wordmark."""
    boy = Text(BED_BOY.strip("\n") + "\n", style="#93c5fd", no_wrap=True)
    boy.highlight_words(["z", "*", "- . -"], "#fde68a")
    boy.highlight_words(["B E D  B O Y"], "bold #c4b5fd")
    word = _gradient(WORDMARK, ["bold #93c5fd", "bold #a5b4fc", "bold #c4b5fd"])
    word.no_wrap = True
    tag = Text(TAGLINE, style="italic")
    if version:
        tag.append(f"  v{version}", style="#a7f3d0")
    return Group(Align.center(boy), Align.center(word), Align.center(tag))


def banner(version: str = "") -> Panel:
    """A compact bedside greeting for annotation runs."""
    head = Text("(-.-) zzz  ", style="#fde68a")
    head.append("BedBoy", style="bold #c4b5fd")
    if version:
        head.append(f" v{version}", style="#a7f3d0")
    head.append(f"  |  {TAGLINE}", style="italic")
    return Panel(head, border_style="#93c5fd", padding=(0, 1), expand=False)


def print_mascot(console: Console | None = None, version: str = "") -> None:
    target = console or Console()
    # Keep narrow terminals readable instead of wrapping the bed and wordmark.
    target.print(mascot(version) if target.width >= 56 else banner(version))


def print_banner(console: Console | None = None, version: str = "") -> None:
    (console or Console()).print(banner(version))
