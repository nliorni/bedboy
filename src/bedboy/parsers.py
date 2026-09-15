"""Convert annotation files into normalised :class:`~bedboy.utils.Gene` records.

Every parser yields gene-body intervals in **0-based half-open** coordinates
with chromosomes run through :func:`bedboy.utils.normalize_chrom`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import unquote

from .utils import (
    Gene,
    bed_fields,
    genepred_offset,
    is_bed_header,
    normalize_chrom,
    open_text,
    valid_interval,
)

_GTF_ATTR = re.compile(r'(\w+)\s+"([^"]*)"')
_GFF_GENE_TYPES = {"gene", "pseudogene", "ncrna_gene", "snrna_gene", "rrna_gene"}


def parse_genepred(path: str) -> Iterator[Gene]:
    """UCSC genePred tables (refGene / ncbiRefSeq), with or without a ``bin`` col.

    genePred ``txStart``/``txEnd`` are already 0-based half-open.
    The gene symbol lives in ``name2``.
    """
    with open_text(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            c = line.rstrip("\r\n").split("\t")
            # Detect a leading 'bin' column. genePred(Ext) layout, after the
            # optional bin: name, chrom, strand, txStart, txEnd, cdsStart,
            # cdsEnd, exonCount, exonStarts, exonEnds, score, name2, ...
            offset = genepred_offset(c)
            if offset is None:
                continue
            c = c[offset:]
            chrom, txs, txe, cds_s, cds_e = c[1], c[3], c[4], c[5], c[6]
            name2 = c[11] if len(c) > 11 and c[11].strip() not in {"", "."} else c[0]
            try:
                start, end = int(txs), int(txe)
                coding = int(cds_s) < int(cds_e)
            except ValueError:
                continue
            name = (name2 or "").strip()
            if name and name != "." and valid_interval(start, end) and start < end:
                # genePred has no biotype column; a non-empty CDS marks coding.
                biotype = "protein_coding" if coding else "non_coding"
                yield Gene(normalize_chrom(chrom), start, end, name, biotype)


def _gtf_attrs(field: str) -> dict[str, str]:
    return {k: v for k, v in _GTF_ATTR.findall(field)}


def parse_gtf(path: str) -> Iterator[Gene]:
    """GENCODE / Ensembl GTF. Uses ``gene`` features when present, else collapses
    transcript/exon lines by ``gene_id``. Coordinates are 1-based -> converted."""
    # IDs may recur on other contigs (e.g. pseudoautosomal X/Y genes).
    genes: dict[tuple[str, str, str], Gene] = {}
    fallback: dict[tuple[str, str, str], Gene] = {}

    with open_text(path) as fh:
        for line in fh:
            if not line or line.startswith("#"):
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) != 9:
                continue
            feature = c[2]
            try:
                start = int(c[3]) - 1  # 1-based inclusive -> 0-based
                end = int(c[4])
            except ValueError:
                continue
            if not valid_interval(start, end) or start == end:
                continue
            attrs = _gtf_attrs(c[8])
            gid = attrs.get("gene_id", "")
            name = attrs.get("gene_name") or gid
            biotype = attrs.get("gene_type") or attrs.get("gene_biotype") or ""
            chrom = normalize_chrom(c[0])
            key = (chrom, c[6], gid or name)
            if not name or name == ".":
                continue

            if feature == "gene":
                genes[key] = Gene(chrom, start, end, name, biotype)
                fallback.pop(key, None)
            elif feature in {"transcript", "exon", "CDS", "start_codon", "stop_codon", "UTR"}:
                if key in genes:
                    continue
                rec = fallback.get(key)
                if rec is None:
                    fallback[key] = Gene(chrom, start, end, name, biotype)
                else:
                    rec.start = min(rec.start, start)
                    rec.end = max(rec.end, end)
                    if attrs.get("gene_name"):
                        rec.name = name
                    if biotype:
                        rec.biotype = biotype

    yield from genes.values()
    yield from fallback.values()


def _gff_attrs(field: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for kv in field.split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k.strip()] = unquote(v.strip())
    return out


def parse_gff3(path: str) -> Iterator[Gene]:
    """GFF3 (e.g. UCSC/GENCODE GFF3). Emits gene-type features. 1-based -> 0-based."""
    with open_text(path) as fh:
        for line in fh:
            if line.rstrip() == "##FASTA":
                break
            if not line or line.startswith("#"):
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) != 9:
                continue
            if c[2].lower() not in _GFF_GENE_TYPES:
                continue
            try:
                start = int(c[3]) - 1
                end = int(c[4])
            except ValueError:
                continue
            a = _gff_attrs(c[8])
            name = a.get("gene_name") or a.get("gene") or a.get("Name") or a.get("ID", "")
            biotype = a.get("gene_biotype") or a.get("gene_type") or a.get("biotype") or ""
            if name and name != "." and valid_interval(start, end) and start < end:
                yield Gene(normalize_chrom(c[0]), start, end, name, biotype)


def parse_bed(path: str) -> Iterator[Gene]:
    """A simple gene-BED: ``chrom  start  end  gene_name[  biotype]`` (0-based)."""
    with open_text(path) as fh:
        for line in fh:
            if is_bed_header(line):
                continue
            c = bed_fields(line)
            if len(c) < 4:
                continue
            try:
                start, end = int(c[1]), int(c[2])
            except ValueError:
                continue
            name = c[3].strip()
            biotype = c[4].strip() if len(c) > 4 and not c[4].strip().isdigit() else ""
            if name and name != "." and valid_interval(start, end) and start < end:
                yield Gene(normalize_chrom(c[0]), start, end, name, biotype)


PARSERS = {
    "genepred": parse_genepred,
    "gtf": parse_gtf,
    "gff3": parse_gff3,
    "bed": parse_bed,
}


def parse(path: str, fmt: str) -> Iterator[Gene]:
    try:
        fn = PARSERS[fmt]
    except KeyError:
        raise ValueError(f"unknown annotation format '{fmt}'") from None
    return fn(path)
