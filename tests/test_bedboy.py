"""End-to-end-ish unit tests for BedBoy."""

import io
from pathlib import Path

import pytest

from bedboy.annotate import annotate_stream, build_index_from_file
from bedboy.parsers import parse
from bedboy.sources import canonical_genome, resolve_source
from bedboy.utils import normalize_chrom, sniff_format

DATA = Path(__file__).parent / "data"


# ----------------------------- utils ---------------------------------------
@pytest.mark.parametrize(
    "raw,expect",
    [
        ("chr1", "1"),
        ("Chr1", "1"),
        ("1", "1"),
        ("chrX", "X"),
        ("chrM", "MT"),
        ("MT", "MT"),
        ("M", "MT"),
    ],
)
def test_normalize_chrom(raw, expect):
    assert normalize_chrom(raw) == expect


def test_sniff_format():
    assert sniff_format(str(DATA / "mini.gtf")) == "gtf"
    assert sniff_format(str(DATA / "mini.genepred")) == "genepred"
    assert sniff_format(str(DATA / "mini.genes.bed")) == "bed"


# ----------------------------- parsers -------------------------------------
def test_parse_genepred_bin_and_coding():
    genes = list(parse(str(DATA / "mini.genepred"), "genepred"))
    by = {g.name: g for g in genes}
    assert by["AAA"].biotype == "protein_coding"  # cdsStart < cdsEnd
    assert by["BBB"].biotype == "non_coding"  # cdsStart == cdsEnd
    # genePred txStart is already 0-based half-open
    assert (by["AAA"].chrom, by["AAA"].start, by["AAA"].end) == ("1", 1000, 2000)


def test_parse_gtf_is_zero_based_halfopen():
    genes = {g.name: g for g in parse(str(DATA / "mini.gtf"), "gtf")}
    # GTF 1-based 1001..2000  ->  0-based half-open 1000..2000
    assert (genes["AAA"].start, genes["AAA"].end) == (1000, 2000)
    assert genes["AAA"].biotype == "protein_coding"


def test_parse_bed():
    genes = {g.name: g for g in parse(str(DATA / "mini.genes.bed"), "bed")}
    assert set(genes) == {"AAA", "BBB", "CCC"}
    assert genes["BBB"].biotype == "lncRNA"


# ----------------------------- engine --------------------------------------
def test_prefer_coding_resolves_overlap():
    idx = build_index_from_file(str(DATA / "mini.genes.bed"), "bed")
    # region 1600-1700 overlaps AAA(coding) and BBB(lncRNA)
    assert idx.query("chr1", 1600, 1700, prefer_coding=True) == ["AAA"]
    assert idx.query("chr1", 1600, 1700, prefer_coding=False) == ["AAA", "BBB"]


def test_chrom_prefix_mismatch_still_matches():
    # index built from 'chr1'; query with bare '1' must still hit
    idx = build_index_from_file(str(DATA / "mini.genes.bed"), "bed")
    assert idx.query("1", 1600, 1700) == ["AAA"]


def test_annotate_stream_appends_column_and_counts():
    idx = build_index_from_file(str(DATA / "mini.genes.bed"), "bed")
    out = io.StringIO()
    stats = annotate_stream(idx, str(DATA / "mini_input.bed"), out)
    lines = out.getvalue().strip().split("\n")
    assert lines[0].split("\t") == ["chr1", "1600", "1700", "AAA"]
    assert lines[1].split("\t")[3] == "CCC"
    assert lines[2].split("\t")[3] == "."  # chr3 miss
    assert stats.total == 3
    assert stats.annotated == 2
    assert stats.unannotated == 1


# ----------------------------- sources -------------------------------------
@pytest.mark.parametrize(
    "alias,canon",
    [
        ("hg19", "hg19"),
        ("grch37", "hg19"),
        ("GRCh38", "hg38"),
        ("chm13", "t2t"),
        ("hs1", "t2t"),
        ("t2t", "t2t"),
    ],
)
def test_genome_aliases(alias, canon):
    assert canonical_genome(alias) == canon


def test_every_default_source_has_https_url():
    for g in ("hg19", "hg38", "t2t"):
        src = resolve_source(g, "refseq")
        assert src.url.startswith("https://")
        assert src.fmt in {"genepred", "gtf", "gff3", "bed"}


def test_unknown_genome_and_source_raise():
    with pytest.raises(KeyError):
        canonical_genome("banana")
    with pytest.raises(KeyError):
        resolve_source("hg38", "nope")
