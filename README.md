<div align="center">

![BedBoy: a sleepy boy tucked under a quilt of genomic intervals. Gene names, without leaving bed.](docs/assets/bedboy.svg)

# BedBoy

**Gene names, without leaving bed.**

A boy who never leaves bed. A BED annotator that gets the work done.

[![CI](https://github.com/nliorni/bedboy/actions/workflows/ci.yml/badge.svg)](https://github.com/nliorni/bedboy/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-93c5fd.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-c4b5fd.svg)](LICENSE)

</div>

## What it does

BedBoy takes an interval BED file (`chrom  start  end`) and appends the
overlapping **gene symbol(s)** as a new column. Existing columns stay in place.
It picks an annotation source for your genome automatically, downloads and
caches it, then does a fast interval overlap.

- 🧬 **hg19 / hg38 / T2T-CHM13** out of the box (plus aliases `grch37`, `grch38`, `chm13`/`hs1`)
- ⚡ **Fast** nested-containment overlap (the engine behind `pyranges`)
- 🤖 **Automatic** — auto-download + cache, auto-detect format, auto-harmonise `chr1` vs `1`
- 🌙 **A sleepy CLI** with a tucked-in mascot, moonlit colors and a tidy report
- 🧵 **Pipeline-friendly** — BED on stdout, diagnostics on stderr, stdin and gzip support
- 🔌 **Bring your own** annotation via `--annotation-file` or `--annotation-url`
- 🧷 Coordinate-system-correct (GTF/GFF 1-based ↔ BED 0-based handled for you)

## Install

From GitHub:

```bash
conda create -n bedboy python=3.11
conda activate bedboy
pip install git+https://github.com/nliorni/bedboy.git
```

From source (editable, for development):

```bash
conda create -n bedboy python=3.11
conda activate bedboy
git clone https://github.com/nliorni/bedboy.git
cd bedboy
pip install -e ".[dev]"
```

## Quick start

```bash
# hg38, RefSeq (default source). Output: targets.bedboy.bed
bedboy annotate targets.bed --genome hg38

# choose a source and an explicit output
bedboy annotate targets.bed -g hg38 -s gencode -o annotated.bed

# T2T-CHM13
bedboy annotate targets.bed -g t2t

# stream to stdout, pipe onward (diagnostics stay on stderr)
bedboy annotate targets.bed -g hg19 -o - | head

# read BED from stdin; stdout is the default for piped input
cat targets.bed | bedboy annotate - -g hg38 -q

# gzip input is detected automatically; .gz output is compressed
bedboy annotate targets.bed.gz -g hg38 -o annotated.bed.gz
```

Input (tab-separated; whitespace-separated BED is also accepted):

```
chr17   7668402   7687550
```

Output:

```
chr17   7668402   7687550   TP53
```

A region overlapping more than one gene gets them joined with `;`
(e.g. `ACAP3;PUSL1`); a region overlapping nothing gets `.`.

### Try it offline

From a source checkout, use the tiny example files without downloading annotations:

```bash
bedboy annotate tests/data/mini_input.bed -g hg38 \
    --annotation-file tests/data/mini.genes.bed -o -
```

Run `bedboy` to meet the mascot, or `bedboy annotate --help` for all options.

## Annotation sources

List what's available (and the exact URLs used):

```bash
bedboy sources               # all genomes
bedboy sources -g hg38       # one genome
```

| genome | `refseq` (default)        | `refgene`              | other                                   |
|--------|---------------------------|------------------------|-----------------------------------------|
| hg19   | UCSC `ncbiRefSeq`         | UCSC `refGene`         | `gencode` → GENCODE v50 (lift37, basic) |
| hg38   | UCSC `ncbiRefSeq`         | UCSC `refGene`         | `gencode` → GENCODE v50 (basic)         |
| t2t    | UCSC `hs1` `ncbiRefSeq`   | —                      | `catliftoff` → UCSC CHM13v2.0 CAT/Liftoff GFF3   |

> **Why UCSC genePred by default?** UCSC provides genePred annotations for hg19, hg38
> **and** hs1 (T2T). BedBoy uses the `database/` table dumps for hg19/hg38
> and the `bigZips/genes/` dumps for hs1, with the same coordinate handling.
> Extended genePred files provide a gene symbol in `name2`; basic 10-column
> genePred files fall back to the transcript identifier.

### Bring your own annotation

```bash
# a local GTF/GFF3/genePred/gene-BED (format auto-detected, override with --format)
bedboy annotate targets.bed -g hg38 --annotation-file my_genes.gtf

# any URL
bedboy annotate targets.bed -g hg38 \
    --annotation-url https://example.org/genes.gff3.gz --format gff3
```

A **gene-BED** is just: `chrom  start  end  gene_name[  biotype]` (0-based).
A numeric fifth column is treated as a BED score, not a biotype.
Choose either `--annotation-file` or `--annotation-url`. Both annotation and
target coordinates must already use the same assembly; `--genome` does not
convert coordinates or perform liftOver.

## Useful options

| option | meaning |
|--------|---------|
| `-g, --genome` | `hg19` \| `hg38` \| `t2t` (required) |
| `-s, --source` | source key, default `refseq` |
| `-o, --output` | output path (`.gz` for gzip), or `-` for stdout |
| `--strict` | reject malformed BED records with a line-numbered error |
| `--annotation-file` / `--annotation-url` | use your own annotation |
| `--format` | force `gtf`/`gff3`/`genepred`/`bed` |
| `--all-biotypes` | don't prefer protein-coding when genes overlap |
| `--join` | separator for multiple genes (default `;`) |
| `--none-label` | label for no-overlap regions (default `.`) |
| `--refresh` | re-download the annotation |
| `--cache-dir` | override cache location |
| `--no-banner` / `--no-color` / `-q` | quieter output |

## Caching

Downloads are cached in `$XDG_CACHE_HOME/bedboy` (default `~/.cache/bedboy`).
`$BEDBOY_CACHE` overrides that location; `--cache-dir` takes precedence over both.
The full URL identifies each cached file. Downloads are written atomically,
and a failed `--refresh` preserves the previous cached copy.

```bash
bedboy cache            # show cached annotations and sizes
bedboy cache --path     # print just the directory, for scripts
bedboy cache --clear    # remove completed BedBoy downloads only
```

## How overlap & gene choice work

- Coordinates are normalised to **0-based half-open** internally; UCSC genePred
  is already 0-based, GTF/GFF (1-based inclusive) is converted.
- Chromosome names are harmonised, so `chr1` ↔ `1` and `chrM` ↔ `chrMT` match.
- A target is assigned every gene whose **gene body** overlaps it; genePred uses
  each transcript span. When several overlap and biotype info is available,
  protein-coding symbols win unless you pass `--all-biotypes`.
- Multiple symbols are deduplicated and sorted for reproducible output.
- GTF uses explicit gene features where available, and collapses transcript/exon
  features for each remaining gene. Genes on different chromosomes stay separate.
- GFF3 uses gene features and decodes percent-escaped names. GTF/GFF3 names fall
  back to gene identifiers when symbols are absent.
- Zero-length targets (`start == end`) overlap no bases and get `--none-label`.
  Touching an interval boundary is not an overlap.

## Input and output behavior

- Comments, blank lines, and `track`/`browser` headers pass through unchanged.
- Malformed BED rows also pass through by default, with a warning and separate
  count. `--strict` rejects them. Negative coordinates, reversed intervals, and
  values outside the signed 64-bit range are malformed.
- Tab-delimited extra columns, including spaces within a field, are preserved.
  Output data rows are tab-delimited. Input files may be plain text or gzip.
- File output is replaced only after a successful run. BedBoy rejects output
  paths that refer to either input file, including symlink and hard-link aliases.
  Streaming to stdout can produce partial output if an error occurs later.
- `-q` suppresses informational messages; errors still appear on stderr.
  `--no-color` and `NO_COLOR=1` disable colors.
- A BED3 input becomes BED4. For input with extra fields, the added gene column
  produces an extended BED-like TSV; downstream tools must support that layout.

## Library use

```python
from bedboy import build_index_from_file, annotate_stream

index = build_index_from_file("genes.gtf", "gtf")
with open("out.bed", "w") as out:
    stats = annotate_stream(index, "targets.bed", out)
print(stats.annotated, "of", stats.total, "regions annotated")
```

## Development

```bash
pip install -e ".[dev]" build hatchling
pytest --cov=bedboy
ruff check .
ruff format --check .
python -m build --no-isolation
```

Tests use local fixtures and mocked downloads; they do not require network access.
CI tests Python 3.10–3.13 and smoke-tests the built wheel. The editable README
illustration lives in [`docs/assets/bedboy.svg`](docs/assets/bedboy.svg); the
terminal mascot lives in [`src/bedboy/art.py`](src/bedboy/art.py).

## Notes & caveats

- Gene-body annotation: an intronic target still gets its host gene's name
  (what you usually want for panel/target labelling).
- T2T sources depend on UCSC `hs1` download availability; if a file moves, use
  `--annotation-url`/`--annotation-file`. `bedboy sources -g t2t` prints the URL.
- UCSC downloads can change upstream. For reproducible runs, archive the exact
  annotation file and use `--annotation-file`; GENCODE URLs pin a release.
- Symbols reflect the chosen release, so very recently renamed genes may differ
  from the latest HGNC nomenclature.

## License

MIT — see [LICENSE](LICENSE).

<div align="center"><sub>(-.-) zzz · stay in BED.</sub></div>
