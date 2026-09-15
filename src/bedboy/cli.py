"""BedBoy command-line interface."""

from __future__ import annotations

import gzip
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import click
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from . import __version__
from .annotate import Stats, annotate_stream, build_index_from_file
from .art import print_banner, print_mascot
from .console import make_console
from .download import DownloadError, fetch
from .sources import (
    canonical_genome,
    list_sources,
    resolve_source,
    sources_for,
)
from .utils import human, sniff_format

CONTEXT = {"help_option_names": ["-h", "--help"]}


def _default_output(inp: str) -> str:
    p = Path(inp)
    name = p.name
    for ext in (".gz", ".bed", ".txt"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
    return str(p.with_name(name + ".bedboy.bed"))


def _die(msg: str, hint: str | None = None) -> None:
    # Click errors remain visible under --quiet and never interpret Rich markup.
    raise click.ClickException(f"{msg}\n{hint}" if hint else msg)


def _check_output(out_path: str | None, *inputs: str | None) -> None:
    if out_path is None:
        return
    target = Path(out_path)
    for source in inputs:
        if source is None or source == "-":
            continue
        path = Path(source)
        if target.resolve() == path.resolve() or (
            target.exists() and path.exists() and target.samefile(path)
        ):
            _die("output must be different from the input BED and annotation files")


@contextmanager
def _output_file(path: str | None):
    """Publish file output only on success, and leave caller-owned stdout open."""
    if path is None:
        yield sys.stdout
        return
    target = Path(path).resolve()
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        temporary = Path(tmp.name)
    try:
        opener = gzip.open if path.lower().endswith(".gz") else open
        with opener(temporary, "wt", encoding="utf-8", newline="\n") as handle:
            yield handle
        if target.exists():
            temporary.chmod(target.stat().st_mode & 0o777)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


@click.group(context_settings=CONTEXT, invoke_without_command=True)
@click.version_option(__version__, "-V", "--version", prog_name="BedBoy")
@click.pass_context
def main(ctx: click.Context) -> None:
    """BedBoy — gene names, without leaving bed. zzz"""
    if ctx.invoked_subcommand is None:
        print_mascot(make_console(), version=__version__)
        click.echo()
        click.echo(ctx.get_help())


@main.command()
@click.argument("input_bed", type=click.Path(exists=True, dir_okay=False, allow_dash=True))
@click.option(
    "-g",
    "--genome",
    required=True,
    help="Genome build: hg19 | hg38 | t2t (aliases: grch37/grch38/chm13).",
)
@click.option(
    "-s",
    "--source",
    default="refseq",
    show_default=True,
    help="Annotation source key (see `bedboy sources`).",
)
@click.option(
    "-o",
    "--output",
    default=None,
    help="Output BED path. Use '-' for stdout. [default: <input>.bedboy.bed]",
)
@click.option(
    "--annotation-file",
    type=click.Path(exists=True, dir_okay=False),
    help="Use a local annotation file instead of a built-in source.",
)
@click.option("--annotation-url", help="Download annotation from a custom URL.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["gtf", "gff3", "genepred", "bed"]),
    help="Force annotation format (otherwise auto-detected).",
)
@click.option(
    "--prefer-coding/--all-biotypes",
    default=True,
    show_default=True,
    help="When several genes overlap, prefer protein-coding symbols.",
)
@click.option(
    "--join", default=";", show_default=True, help="Separator for multiple overlapping gene names."
)
@click.option(
    "--none-label",
    default=".",
    show_default=True,
    help="Label written when no gene overlaps a region.",
)
@click.option("--cache-dir", default=None, help="Override the annotation cache directory.")
@click.option("--refresh", is_flag=True, help="Force re-download of the annotation.")
@click.option(
    "--strict", is_flag=True, help="Fail on malformed BED records instead of passing them through."
)
@click.option("--no-banner", is_flag=True, help="Do not print the banner.")
@click.option("--no-color", is_flag=True, help="Disable coloured output.")
@click.option("-q", "--quiet", is_flag=True, help="Only print errors.")
def annotate(
    input_bed,
    genome,
    source,
    output,
    annotation_file,
    annotation_url,
    fmt,
    prefer_coding,
    join,
    none_label,
    cache_dir,
    refresh,
    strict,
    no_banner,
    no_color,
    quiet,
):
    """Annotate INPUT_BED, appending a gene-name column. Use '-' for stdin."""
    console = make_console(no_color=no_color, quiet=quiet)
    if not no_banner and not quiet:
        print_banner(console, version=__version__)

    # --- resolve genome ---
    try:
        gkey = canonical_genome(genome)
    except KeyError as e:
        _die(e.args[0])

    if annotation_file and annotation_url:
        raise click.UsageError("--annotation-file and --annotation-url are mutually exclusive")
    for option, value in (("--join", join), ("--none-label", none_label)):
        if any(c in value for c in "\t\r\n"):
            raise click.BadParameter("must not contain tabs or newlines", param_hint=option)
    if input_bed == "-" and output is None:
        output = "-"
    out_path = None if output == "-" else (output or _default_output(input_bed))
    try:
        _check_output(out_path, input_bed, annotation_file)
    except OSError as e:
        _die(str(e))

    # --- resolve annotation (file > url > built-in source) ---
    try:
        if annotation_file:
            ann_path = annotation_file
            ann_fmt = fmt or sniff_format(ann_path)
            label = f"local file ({ann_fmt})"
        elif annotation_url:
            ann_path = str(fetch(annotation_url, console=console, cache=cache_dir, force=refresh))
            ann_fmt = fmt or sniff_format(ann_path)
            label = f"custom URL ({ann_fmt})"
        else:
            src = resolve_source(gkey, source)
            if src.note and not quiet:
                console.print(f"[bb.muted]note: {src.note}[/bb.muted]")
            ann_path = str(fetch(src.url, console=console, cache=cache_dir, force=refresh))
            ann_fmt = fmt or src.fmt
            label = src.label
    except DownloadError as e:
        _die(
            str(e),
            "Try a different --source, pass --annotation-url, or "
            "download manually and use --annotation-file.",
        )
    except KeyError as e:
        _die(e.args[0])
    except (OSError, ValueError, EOFError) as e:
        _die(f"could not read annotation: {e}")

    # --- build the gene index ---
    if not quiet:
        console.print(
            f"[bb.accent]annotation:[/bb.accent] {escape(label)}  [bb.muted]({gkey})[/bb.muted]"
        )
    with Progress(
        SpinnerColumn(),
        TextColumn("[bb.accent]building gene index[/bb.accent]"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
        disable=quiet or not console.is_terminal,
    ) as p:
        p.add_task("idx", total=None)
        try:
            index = build_index_from_file(ann_path, ann_fmt)
        except (OSError, ValueError, EOFError, OverflowError) as e:
            _die(f"failed to parse annotation: {e}")
    if index.n_genes == 0:
        _die(
            "no genes parsed from the annotation source.",
            "Check --format, or the file may be empty/unsupported.",
        )
    if not quiet:
        console.print(
            f"  [bb.ok]✓[/bb.ok] indexed [bb.num]{human(index.n_genes)}[/bb.num] gene models"
        )

    # --- annotate ---
    counter = {"n": 0}
    with Progress(
        SpinnerColumn(),
        TextColumn("[bb.accent]annotating regions[/bb.accent]"),
        TextColumn("[bb.num]{task.fields[n]}[/bb.num]"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
        disable=quiet or not console.is_terminal,
    ) as p:
        task = p.add_task("ann", total=None, n=0)

        def tick():
            counter["n"] += 1
            if counter["n"] % 2000 == 0:
                p.update(task, n=human(counter["n"]))

        try:
            _check_output(out_path, input_bed, ann_path)
            with _output_file(out_path) as out_fh:
                stats = annotate_stream(
                    index,
                    sys.stdin if input_bed == "-" else input_bed,
                    out_fh,
                    prefer_coding=prefer_coding,
                    join=join,
                    none_label=none_label,
                    progress_cb=tick,
                    strict=strict,
                )
        except BrokenPipeError:
            raise  # Click handles downstream consumers such as `head`.
        except (OSError, ValueError, EOFError, OverflowError) as e:
            _die(f"could not annotate BED: {e}")

    if not quiet:
        _print_summary(console, stats, index.n_genes, out_path, none_label)
        if stats.invalid:
            console.print(
                f"[bb.warn]{human(stats.invalid)} malformed BED record(s) passed through "
                "unchanged; use --strict to reject them.[/bb.warn]"
            )
        if stats.total and stats.annotated == 0:
            console.print(
                "[bb.warn]⚠ 0% annotated — chromosome names or genome "
                "build may not match the annotation.[/bb.warn]"
            )


def _print_summary(console, stats: Stats, n_genes: int, out_path, none_label) -> None:
    t = Table(
        title="[bb.brand]BedBoy report[/bb.brand]",
        title_justify="left",
        show_header=False,
        box=None,
        pad_edge=False,
    )
    t.add_column(style="bb.muted")
    t.add_column(style="bold", overflow="fold")
    t.add_row("regions", human(stats.total))
    t.add_row("annotated", f"{human(stats.annotated)}  [bb.ok]({stats.pct_annotated:.1f}%)[/bb.ok]")
    t.add_row("multi-gene", human(stats.multi))
    t.add_row(f"no gene ('{escape(none_label)}')", human(stats.unannotated))
    if stats.passthrough:
        t.add_row("passthrough lines", human(stats.passthrough))
    t.add_row("gene models", human(n_genes))
    t.add_row("output", escape(str(out_path)) if out_path else "<stdout>")
    console.print(t)
    console.print("[bb.brand](-.-) zzz  stay in BED.[/bb.brand]")


@main.command()
@click.option(
    "-g", "--genome", default=None, help="Show sources for one genome only (hg19/hg38/t2t)."
)
@click.option("--no-color", is_flag=True)
def sources(genome, no_color):
    """List built-in annotation sources."""
    console = make_console(no_color=no_color, stderr=False)
    try:
        genomes = [canonical_genome(genome)] if genome else list(list_sources())
    except KeyError as e:
        _die(e.args[0])
    for g in genomes:
        table = Table(
            title=f"[bb.brand]{g}[/bb.brand] sources",
            title_justify="left",
            header_style="bb.accent",
        )
        table.add_column("key", style="bb.gene")
        table.add_column("description")
        table.add_column("format", style="bb.muted")
        table.add_column("url", style="bb.path", overflow="fold")
        for key, src in sources_for(g).items():
            table.add_row(key, src.label, src.fmt, src.url)
        console.print(table)
        console.print()


@main.command()
@click.option("--path", "show_path", is_flag=True, help="Print the cache directory.")
@click.option("--clear", "do_clear", is_flag=True, help="Delete completed BedBoy downloads only.")
@click.option("--cache-dir", default=None)
@click.option("--no-color", is_flag=True)
def cache(show_path, do_clear, cache_dir, no_color):
    """Inspect or clear the annotation cache."""
    console = make_console(no_color=no_color, stderr=False)
    from .download import cache_dir as _cdir
    from .download import cached_files

    if show_path and do_clear:
        raise click.UsageError("--path and --clear are mutually exclusive")
    try:
        path = _cdir(cache_dir)
        if show_path:
            click.echo(str(path))
            return
        files = cached_files(path)
        if do_clear:
            for f in files:
                f.unlink()
            console.print(
                f"[bb.ok]cleared[/bb.ok] {len(files)} file(s) from "
                f"[bb.path]{escape(str(path))}[/bb.path]"
            )
        else:
            console.print(f"[bb.path]{escape(str(path))}[/bb.path]")
            for f in files:
                console.print(f"  [bb.muted]{f.stat().st_size:>12,}[/bb.muted]  {escape(f.name)}")
            if not files:
                console.print("  [bb.muted](empty)[/bb.muted]")
    except OSError as e:
        _die(f"could not access cache: {e}")


if __name__ == "__main__":
    main()
