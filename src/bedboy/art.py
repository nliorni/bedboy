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

# The Bad Boy himself: shades, smirk, cigarette + smoke, popped leather collar.
BAD_BOY = r"""
              .===========.
             //           \\           °
            //   ___   ___  \\        o
       _.--'|   |▛▀▜| |▛▀▜|  |'--._   °
     ⌐(_____|===|▙▄▟|=|▙▄▟|==|_____)¬ o
            |   '═══' '═══'  |       °
            |       ▼        |      ˚
            |     .------.   |═════►   deal with it
            |      '.____.-' |
             \\___________ //
           _.-'|          |'-._
          /  / |          | \  \
         / L/  | B E D B  |  \J \
        / E /  |  O Y     |   \A \
       |__/____|__________|____\__|
        ║▌▌                  ▐▐║
"""

TAGLINE = "the baddest BED annotator in the genome"


def _gradient(text: str, colors: list[str]) -> Text:
    """Apply a vertical colour gradient (one colour per line)."""
    out = Text()
    lines = text.strip("\n").splitlines()
    for i, line in enumerate(lines):
        c = colors[min(i * len(colors) // max(len(lines), 1), len(colors) - 1)]
        out.append(line + "\n", style=c)
    return out


def mascot(version: str = "") -> Group:
    """Full mascot + wordmark, gloriously coloured."""
    boy = Text()
    for line in BAD_BOY.strip("\n").splitlines():
        styled = Text(line + "\n")
        # shades / lenses + the deal-with-it frame
        styled.highlight_words(["▛▀▜", "▙▄▟", "'═══'", "⌐", "¬", "==="], "bold cyan")
        # cigarette + rising smoke + caption
        styled.highlight_words(["►", "˚", "°", " o", "deal with it"], "dim white")
        # popped leather-jacket collar
        styled.highlight_words(["▌▌", "▐▐", "║"], "bold yellow")
        # the logo across the chest
        styled.highlight_words(["B E D B", "O Y"], "bold red")
        boy.append_text(styled)

    word = _gradient(
        WORDMARK,
        ["bold red", "bold red", "bold yellow", "bold yellow", "bold magenta", "bold magenta"],
    )
    tag = Text(f"  {TAGLINE}", style="italic bright_black")
    ver = Text(f"  v{version}" if version else "", style="bold green")

    return Group(
        Align.center(boy),
        Align.center(word),
        Align.center(Text.assemble(tag, ver)),
    )


def banner(version: str = "") -> Panel:
    """Compact one-line-ish banner shown at the top of commands."""
    head = Text()
    head.append("⌐■-■  ", style="bold cyan")
    head.append("BedBoy", style="bold red")
    if version:
        head.append(f" v{version}", style="bold green")
    head.append("  —  ", style="bright_black")
    head.append(TAGLINE, style="italic bright_black")
    return Panel(head, border_style="red", padding=(0, 1), expand=False)


def print_mascot(console: Console | None = None, version: str = "") -> None:
    (console or Console()).print(mascot(version))


def print_banner(console: Console | None = None, version: str = "") -> None:
    (console or Console()).print(banner(version))
