"""Annotation boundary and format regressions."""

import gzip
import io
import random

import pytest

from bedboy import Gene, GeneIndex, annotate_stream
from bedboy.parsers import parse
from bedboy.utils import MAX_COORD, sniff_format


def write(tmp_path, text, name="annotation"):
    path = tmp_path / name
    path.write_text(text)
    return path


@pytest.mark.parametrize("bin_column", ["", "585\t"])
def test_ten_column_genepred_and_optional_bin(tmp_path, bin_column):
    path = write(tmp_path, bin_column + "NM_1\tchr1\t+\t100\t200\t110\t190\t1\t100\t200\n")
    assert sniff_format(path) == "genepred"
    assert list(parse(path, "genepred")) == [Gene("1", 100, 200, "NM_1", "protein_coding")]


def test_bed12_blocks_are_not_mistaken_for_genepred(tmp_path):
    path = write(
        tmp_path, 'track name="genes"\nchr1\t100\t200\tGENE\t0\t+\t100\t200\t0\t2\t20,20\t0,80\n'
    )
    assert sniff_format(path) == "bed"
    assert list(parse(path, "bed"))[0].name == "GENE"


@pytest.mark.parametrize(
    "attrs,expected",
    [
        ("ID=gene1", "gff3"),
        ("Name=GENE", "gff3"),
        ('gene_id "g1"; gene_name "A=B";', "gtf"),
    ],
)
def test_sniff_single_gff_attribute_and_gtf_equals(tmp_path, attrs, expected):
    path = write(tmp_path, f"chr1\tTEST\tgene\t1\t10\t.\t+\t.\t{attrs}\n")
    assert sniff_format(path) == expected


def test_gff_decoding_biotype_and_fasta_stop(tmp_path):
    line = "chr1\tTEST\tgene\t1\t10\t.\t+\t.\tID=g1;Name=A%3BB;gene_type=protein_coding\n"
    path = write(tmp_path, line + "##FASTA\n>chr1\nACGT\n" + line)
    assert list(parse(path, "gff3")) == [Gene("1", 0, 10, "A;B", "protein_coding")]


def test_gtf_mixed_features_keep_fallback_genes_and_chromosomes(tmp_path):
    path = write(
        tmp_path,
        'chrX\tTEST\tgene\t101\t200\t.\t+\t.\tgene_id "shared"; gene_name "XY";\n'
        'chrY\tTEST\tgene\t301\t400\t.\t+\t.\tgene_id "shared"; gene_name "XY";\n'
        'chr1\tTEST\texon\t501\t520\t.\t+\t.\tgene_id "g2";\n'
        'chr1\tTEST\texon\t581\t600\t.\t+\t.\tgene_id "g2"; gene_name "FALLBACK"; gene_biotype "protein_coding";\n'
        'chrX\tTEST\texon\t1\t900\t.\t+\t.\tgene_id "shared"; gene_name "XY";\n',
    )
    genes = list(parse(path, "gtf"))
    assert Gene("X", 100, 200, "XY") in genes
    assert Gene("Y", 300, 400, "XY") in genes
    assert Gene("1", 500, 600, "FALLBACK", "protein_coding") in genes
    assert len(genes) == 3


@pytest.mark.parametrize(
    "fmt,line",
    [
        ("bed", "chr1\t-1\t10\tBAD\nchr1\t0\t10\t.\n"),
        ("gtf", 'chr1\tTEST\tgene\t0\t10\t.\t+\t.\tgene_id "BAD";\n'),
        ("gff3", "chr1\tTEST\tgene\t10\t1\t.\t+\t.\tID=BAD\n"),
        ("genepred", "NM_1\tchr1\t+\t-1\t10\t0\t10\t1\t0,\t10,\n"),
    ],
)
def test_invalid_annotation_intervals_are_skipped(tmp_path, fmt, line):
    assert list(parse(write(tmp_path, line), fmt)) == []


def test_gzip_magic_bom_and_pathlike(tmp_path):
    path = tmp_path / "compressed"
    path.write_bytes(gzip.compress(b"\xef\xbb\xbfchr1\t0\t10\tGENE\r\n"))
    assert sniff_format(path) == "bed"
    assert list(parse(path, "bed")) == [Gene("1", 0, 10, "GENE")]


def test_direct_index_build_normalizes_chromosomes_and_deduplicates():
    index = GeneIndex.build([Gene("chr1", 10, 20, "A"), Gene("1", 10, 20, "A")])
    assert index.query("1", 10, 20) == ["A"]
    assert index.query("chr1", 10, 20) == ["A"]
    assert index.query("1", 0, 10) == []
    assert index.query("1", 20, 30) == []
    assert index.query("1", 15, 15) == []


@pytest.mark.parametrize("start,end", [(-1, 10), (10, 9), (0, MAX_COORD + 1)])
def test_invalid_queries_never_reach_native_index(start, end):
    index = GeneIndex.build([Gene("1", 0, 10, "A")])
    with pytest.raises(ValueError, match="invalid BED interval"):
        index.query("1", start, end)
    with pytest.raises(ValueError, match="invalid gene interval"):
        GeneIndex.build([Gene("1", start, end, "A")])


def test_stream_headers_contigs_invalid_rows_and_extra_columns():
    index = GeneIndex.build([Gene("track1", 0, 10, "A"), Gene("1", 0, 10, "B")])
    incoming = io.StringIO(
        '# comment\n  track name="x"\n\ntrack1\t1\t2\tlabel with spaces\r\n'
        "chr1 1 2\nchr1\t5\t5\nchr1\t-1\t2\nbroken\n"
    )
    out = io.StringIO()
    stats = annotate_stream(index, incoming, out)
    assert not incoming.closed
    assert "track1\t1\t2\tlabel with spaces\tA\n" in out.getvalue()
    assert "chr1\t1\t2\tB\n" in out.getvalue()
    assert "chr1\t5\t5\t.\n" in out.getvalue()
    assert stats.total == 3
    assert stats.annotated == 2
    assert stats.unannotated == 1
    assert stats.passthrough == 5
    assert stats.invalid == 2


def test_randomized_index_matches_simple_half_open_overlap():
    rng = random.Random(42)
    genes = []
    for i in range(150):
        start = rng.randrange(1000)
        genes.append(
            Gene(
                "1",
                start,
                start + rng.randrange(1, 100),
                f"G{i % 30}",
                "protein_coding" if i % 3 else "lncRNA",
            )
        )
    index = GeneIndex.build(genes)
    for _ in range(150):
        start = rng.randrange(1100)
        end = start + rng.randrange(0, 100)
        for prefer in (True, False):
            hits = [g for g in genes if start < end and g.start < end and g.end > start]
            if prefer and any(g.biotype == "protein_coding" for g in hits):
                hits = [g for g in hits if g.biotype == "protein_coding"]
            assert index.query("chr1", start, end, prefer_coding=prefer) == sorted(
                {g.name for g in hits}
            )


def test_t2t_catliftoff_uses_assembly_hub_gff3():
    from bedboy.sources import resolve_source

    source = resolve_source("t2t", "catliftoff")
    assert source.fmt == "gff3"
    assert source.url.endswith("GCA_009914755.4/genes/catLiftOffGenesV1.gff3.gz")
