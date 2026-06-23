"""BedBoy command-line interface."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from . import __version__
from .annotate import Stats, annotate_stream, build_index_from_file
from .art import print_banner, print_mascot
from .console import make_console
from .download import DownloadError, fetch
from .parsers import parse  # noqa: F401  (kept for completeness / re-export)
from .sources import (
    canonical_genome,
    list_sources,
    resolve_source,
    sources_for,
)
from .utils import human, sniff_format

CONTEXT = dict(help_option_names=["-h", "--help"])


def _default_output(inp: str) -> str:
    p = Path(inp)
    name = p.name
    for ext in (".gz", ".bed", ".txt"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
    return str(p.with_name(name + ".bedboy.bed"))


def _die(console, msg: str, hint: str | None = None) -> None:
    console.print(f"[bb.err]✗ {msg}[/bb.err]")
    if hint:
        console.print(f"  [bb.muted]{hint}[/bb.muted]")
    sys.exit(1)


@click.group(context_settings=CONTEXT, invoke_without_command=True)
@click.version_option(__version__, "-V", "--version", prog_name="BedBoy")
@click.pass_context
def main(ctx: click.Context) -> None:
    """BedBoy — annotate BED intervals with gene names. ⌐■-■"""
    if ctx.invoked_subcommand is None:
        print_mascot(make_console(), version=__version__)
        click.echo()
        click.echo(ctx.get_help())


@main.command()
@click.argument("input_bed", type=click.Path(exists=True, dir_okay=False))
@click.option("-g", "--genome", required=True,
              help="Genome build: hg19 | hg38 | t2t (aliases: grch37/grch38/chm13).")
@click.option("-s", "--source", default="refseq", show_default=True,
              help="Annotation source key (see `bedboy sources`).")
@click.option("-o", "--output", default=None,
              help="Output BED path. Use '-' for stdout. [default: <input>.bedboy.bed]")
@click.option("--annotation-file", type=click.Path(exists=True, dir_okay=False),
              help="Use a local annotation file instead of a built-in source.")
@click.option("--annotation-url", help="Download annotation from a custom URL.")
@click.option("--format", "fmt", type=click.Choice(["gtf", "gff3", "genepred", "bed"]),
              help="Force annotation format (otherwise auto-detected).")
@click.option("--prefer-coding/--all-biotypes", default=True, show_default=True,
              help="When several genes overlap, prefer protein-coding symbols.")
@click.option("--join", default=";", show_default=True,
              help="Separator for multiple overlapping gene names.")
@click.option("--none-label", default=".", show_default=True,
              help="Label written when no gene overlaps a region.")
@click.option("--cache-dir", default=None, help="Override the annotation cache directory.")
@click.option("--refresh", is_flag=True, help="Force re-download of the annotation.")
@click.option("--no-banner", is_flag=True, help="Do not print the banner.")
@click.option("--no-color", is_flag=True, help="Disable coloured output.")
@click.option("-q", "--quiet", is_flag=True, help="Only print errors.")
def annotate(input_bed, genome, source, output, annotation_file, annotation_url,
             fmt, prefer_coding, join, none_label, cache_dir, refresh,
             no_banner, no_color, quiet):
    """Annotate INPUT_BED, appending a gene-name column."""
    console = make_console(no_color=no_color, quiet=quiet)
    if not no_banner and not quiet:
        print_banner(console, version=__version__)

    # --- resolve genome ---
    try:
        gkey = canonical_genome(genome)
    except KeyError as e:
        _die(console, str(e))

    # --- resolve annotation (file > url > built-in source) ---
    try:
        if annotation_file:
            ann_path = annotation_file
            ann_fmt = fmt or sniff_format(ann_path)
            label = f"local file ({ann_fmt})"
        elif annotation_url:
            ann_path = str(fetch(annotation_url, console=console,
                                 cache=cache_dir, force=refresh))
            ann_fmt = fmt or sniff_format(ann_path)
            label = f"custom URL ({ann_fmt})"
        else:
            src = resolve_source(gkey, source)
            if src.note and not quiet:
                console.print(f"[bb.muted]note: {src.note}[/bb.muted]")
            ann_path = str(fetch(src.url, console=console,
                                 cache=cache_dir, force=refresh))
            ann_fmt = fmt or src.fmt
            label = src.label
    except DownloadError as e:
        _die(console, str(e),
             "Try a different --source, pass --annotation-url, or "
             "download manually and use --annotation-file.")
    except KeyError as e:
        _die(console, str(e))

    # --- build the gene index ---
    if not quiet:
        console.print(f"[bb.accent]annotation:[/bb.accent] {label}  "
                      f"[bb.muted]({gkey})[/bb.muted]")
    with Progress(SpinnerColumn(), TextColumn("[bb.accent]building gene index[/bb.accent]"),
                  TimeElapsedColumn(), console=console, transient=True,
                  disable=quiet) as p:
        p.add_task("idx", total=None)
        try:
            index = build_index_from_file(ann_path, ann_fmt)
        except Exception as e:  # noqa: BLE001
            _die(console, f"failed to parse annotation: {e}")
    if index.n_genes == 0:
        _die(console, "no genes parsed from the annotation source.",
             "Check --format, or the file may be empty/unsupported.")
    if not quiet:
        console.print(f"  [bb.ok]✓[/bb.ok] indexed [bb.num]{human(index.n_genes)}[/bb.num] gene models")

    # --- resolve output ---
    to_stdout = output == "-"
    out_path = None if to_stdout else (output or _default_output(input_bed))

    # --- annotate ---
    counter = {"n": 0}
    with Progress(SpinnerColumn(), TextColumn("[bb.accent]annotating regions[/bb.accent]"),
                  TextColumn("[bb.num]{task.fields[n]}[/bb.num]"), TimeElapsedColumn(),
                  console=console, transient=True, disable=quiet) as p:
        task = p.add_task("ann", total=None, n=0)

        def tick():
            counter["n"] += 1
            if counter["n"] % 2000 == 0:
                p.update(task, n=human(counter["n"]))

        out_fh = sys.stdout if to_stdout else open(out_path, "w", encoding="utf-8")
        try:
            stats = annotate_stream(index, input_bed, out_fh,
                                    prefer_coding=prefer_coding, join=join,
                                    none_label=none_label, progress_cb=tick)
        finally:
            if not to_stdout:
                out_fh.close()

    if not quiet:
        _print_summary(console, stats, index.n_genes, out_path, none_label)
        if stats.total and stats.annotated == 0:
            console.print("[bb.warn]⚠ 0% annotated — chromosome names or genome "
                          "build may not match the annotation.[/bb.warn]")


def _print_summary(console, stats: Stats, n_genes: int, out_path, none_label) -> None:
    t = Table(title="[bb.brand]BedBoy report[/bb.brand]", title_justify="left",
              show_header=False, box=None, pad_edge=False)
    t.add_column(style="bb.muted")
    t.add_column(style="bold")
    t.add_row("regions", human(stats.total))
    t.add_row("annotated", f"{human(stats.annotated)}  "
                           f"[bb.ok]({stats.pct_annotated:.1f}%)[/bb.ok]")
    t.add_row("multi-gene", human(stats.multi))
    t.add_row(f"no gene ('{none_label}')", human(stats.unannotated))
    if stats.passthrough:
        t.add_row("passthrough lines", human(stats.passthrough))
    t.add_row("gene models", human(n_genes))
    t.add_row("output", str(out_path) if out_path else "<stdout>")
    console.print(t)
    console.print("[bb.brand]⌐■-■ stay bad.[/bb.brand]")


@main.command()
@click.option("-g", "--genome", default=None,
              help="Show sources for one genome only (hg19/hg38/t2t).")
@click.option("--no-color", is_flag=True)
def sources(genome, no_color):
    """List built-in annotation sources."""
    console = make_console(no_color=no_color)
    genomes = [canonical_genome(genome)] if genome else list(list_sources())
    for g in genomes:
        table = Table(title=f"[bb.brand]{g}[/bb.brand] sources",
                      title_justify="left", header_style="bb.accent")
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
@click.option("--clear", "do_clear", is_flag=True, help="Delete all cached annotations.")
@click.option("--cache-dir", default=None)
@click.option("--no-color", is_flag=True)
def cache(show_path, do_clear, cache_dir, no_color):
    """Inspect or clear the annotation cache."""
    console = make_console(no_color=no_color)
    from .download import cache_dir as _cdir
    path = _cdir(cache_dir)
    if do_clear:
        n = 0
        for f in path.glob("*"):
            if f.is_file():
                f.unlink()
                n += 1
        console.print(f"[bb.ok]cleared[/bb.ok] {n} file(s) from [bb.path]{path}[/bb.path]")
    else:
        console.print(f"[bb.path]{path}[/bb.path]")
        files = sorted(path.glob("*"))
        for f in files:
            if f.is_file():
                console.print(f"  [bb.muted]{f.stat().st_size:>12,}[/bb.muted]  {f.name}")
        if not files:
            console.print("  [bb.muted](empty)[/bb.muted]")


if __name__ == "__main__":
    main()
