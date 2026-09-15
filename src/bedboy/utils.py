"""Small shared helpers: gene records, chromosome harmonisation, IO sniffing."""

from __future__ import annotations

import gzip
import io
import os
import re
from dataclasses import dataclass

MAX_COORD = (1 << 63) - 1  # NCLS uses signed 64-bit coordinates.


def valid_interval(start: int, end: int) -> bool:
    return 0 <= start <= end <= MAX_COORD


def is_bed_header(line: str) -> bool:
    """Recognise header words without swallowing contigs such as ``track1``."""
    stripped = line.lstrip()
    return (
        not stripped.strip()
        or stripped.startswith("#")
        or stripped.split(maxsplit=1)[0] in {"track", "browser"}
    )


def bed_fields(line: str) -> list[str]:
    """Preserve tab-separated extra columns; also accept whitespace BED."""
    line = line.rstrip("\r\n")
    return line.split("\t") if "\t" in line else line.split()


def genepred_offset(cols: list[str]) -> int | None:
    """Locate the optional UCSC bin column by the genePred strand field."""
    if len(cols) >= 10 and cols[2] in {"+", "-"}:
        return 0
    if len(cols) >= 11 and cols[0].isdigit() and cols[3] in {"+", "-"}:
        return 1
    return None


@dataclass(slots=True)
class Gene:
    """A gene-body interval in 0-based half-open coordinates."""

    chrom: str  # normalised chromosome key (see normalize_chrom)
    start: int  # 0-based, inclusive
    end: int  # 0-based, exclusive
    name: str  # gene symbol
    biotype: str = ""  # e.g. protein_coding (may be empty for some sources)


def normalize_chrom(chrom: str) -> str:
    """Normalise a chromosome name so 'chr1' and '1' (etc.) compare equal.

    Strips a leading ``chr``/``Chr``, upper-cases, and folds the mitochondrion
    aliases (``M``/``MT``) together so naming differences between a BED file and
    its annotation source never cause silent misses.
    """
    c = chrom.strip()
    if c[:3].lower() == "chr":
        c = c[3:]
    c = c.upper()
    if c in ("M", "MT"):
        return "MT"
    return c


def open_text(path: str | os.PathLike[str]) -> io.TextIOBase:
    """Open a plain or gzip-compressed text file transparently."""
    with open(path, "rb") as fh:
        magic = fh.read(2)
    if magic == b"\x1f\x8b":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8-sig")
    return open(path, encoding="utf-8-sig")


def sniff_format(path: str | os.PathLike[str]) -> str:
    """Best-effort detection of an annotation file format.

    Returns one of: ``gtf``, ``gff3``, ``genepred``, ``bed``.
    """
    lower = os.fspath(path).lower()
    for ext, fmt in (
        (".gtf", "gtf"),
        (".gff3", "gff3"),
        (".gff", "gff3"),
        (".genepred", "genepred"),
        (".gp", "genepred"),
        (".bed", "bed"),
    ):
        if lower.endswith(ext) or lower.endswith(ext + ".gz"):
            return fmt

    # Otherwise peek at the first real data line.
    with open_text(path) as fh:
        for line in fh:
            if is_bed_header(line):
                if line.startswith("##gff-version"):
                    return "gff3"
                continue
            cols = line.rstrip("\r\n").split("\t")
            # GTF/GFF have 9 columns with a key/value attribute field at the end.
            if len(cols) == 9 and cols[6] in {"+", "-", ".", "?"}:
                if re.search(r'\w+\s+"', cols[8]):
                    return "gtf"
                if "=" in cols[8]:
                    return "gff3"
            # BED12 also contains comma-separated blocks; check the layout.
            if genepred_offset(cols) is not None:
                return "genepred"
            # Fall back to BED: gene name expected in column 4.
            return "bed"
    return "bed"


def human(n: int) -> str:
    """Thousands-separated integer for friendly output."""
    return f"{n:,}"
