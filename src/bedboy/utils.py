"""Small shared helpers: gene records, chromosome harmonisation, IO sniffing."""
from __future__ import annotations

import gzip
import io
from dataclasses import dataclass


@dataclass(slots=True)
class Gene:
    """A gene-body interval in 0-based half-open coordinates."""

    chrom: str          # normalised chromosome key (see normalize_chrom)
    start: int          # 0-based, inclusive
    end: int            # 0-based, exclusive
    name: str           # gene symbol
    biotype: str = ""   # e.g. protein_coding (may be empty for some sources)


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


def open_text(path: str) -> io.TextIOBase:
    """Open a plain or gzip-compressed text file transparently."""
    with open(path, "rb") as fh:
        magic = fh.read(2)
    if magic == b"\x1f\x8b":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def sniff_format(path: str) -> str:
    """Best-effort detection of an annotation file format.

    Returns one of: ``gtf``, ``gff3``, ``genepred``, ``bed``.
    """
    lower = path.lower()
    for ext, fmt in (
        (".gtf", "gtf"),
        (".gff3", "gff3"),
        (".gff", "gff3"),
        (".genepred", "genepred"),
    ):
        if lower.endswith(ext) or lower.endswith(ext + ".gz"):
            return fmt

    # Otherwise peek at the first real data line.
    with open_text(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                if line.startswith("##gff-version"):
                    return "gff3"
                continue
            cols = line.rstrip("\n").split("\t")
            # GTF/GFF have 9 columns with a key/value attribute field at the end.
            if len(cols) == 9 and ("gene_id " in cols[8] or "ID=" in cols[8] or "gene_name " in cols[8]):
                return "gff3" if "=" in cols[8] and ";" in cols[8] and "gene_id " not in cols[8] else "gtf"
            # genePred (refGene/ncbiRefSeq) has >=10 cols, exonStarts contain commas.
            if len(cols) >= 10 and "," in line:
                return "genepred"
            # Fall back to BED: gene name expected in column 4.
            return "bed"
    return "bed"


def human(n: int) -> str:
    """Thousands-separated integer for friendly output."""
    return f"{n:,}"
