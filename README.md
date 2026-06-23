<div align="center">

# BedBoy ⌐■-■

**The BEDdest annotator in the world**

Give it an unannotated BED file and a genome build — it adds a gene-name column. That's it.

[![CI](https://github.com/your-org/bedboy/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/bedboy/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## What it does

BedBoy takes a plain interval BED file (`chrom  start  end`) and appends a fourth
column containing the overlapping **gene symbol(s)**. It picks a sensible
annotation source for your genome automatically, downloads and caches it, then
does a fast interval overlap.

- 🧬 **hg19 / hg38 / T2T-CHM13** out of the box (plus aliases `grch37`, `grch38`, `chm13`/`hs1`)
- ⚡ **Fast** nested-containment overlap (the engine behind `pyranges`)
- 🤖 **Automatic** — auto-download + cache, auto-detect format, auto-harmonise `chr1` vs `1`
- 🎨 **Colorful CLI** with progress bars and a tidy report
- 🔌 **Bring your own** annotation via `--annotation-file` or `--annotation-url`
- 🧷 Coordinate-system-correct (GTF/GFF 1-based ↔ BED 0-based handled for you)

## Install


Or straight from GitHub:

```bash
pip install git+https://github.com/your-org/bedboy.git
```

From source (editable, for development):

```bash
git clone https://github.com/your-org/bedboy.git
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

# stream to stdout, pipe onward
bedboy annotate targets.bed -g hg19 -o - | head
```

Input:

```
chr17   7668402   7687550
```

Output:

```
chr17   7668402   7687550   TP53
```

A region overlapping more than one gene gets them joined with `;`
(e.g. `ACAP3;PUSL1`); a region overlapping nothing gets `.`.

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
| t2t    | UCSC `hs1` `ncbiRefSeq`   | —                      | `catliftoff` → UCSC `hs1` CAT/Liftoff   |

> **Why UCSC genePred by default?** Those tables exist uniformly for hg19, hg38
> **and** hs1 (T2T), use `chr`-prefixed names that match most BED files, and put
> the gene symbol in a single column — so behaviour is consistent across builds.

### Bring your own annotation

```bash
# a local GTF/GFF3/genePred/gene-BED (format auto-detected, override with --format)
bedboy annotate targets.bed -g hg38 --annotation-file my_genes.gtf

# any URL
bedboy annotate targets.bed -g hg38 \
    --annotation-url https://example.org/genes.gff3.gz --format gff3
```

A **gene-BED** is just: `chrom  start  end  gene_name[  biotype]` (0-based).

## Useful options

| option | meaning |
|--------|---------|
| `-g, --genome` | `hg19` \| `hg38` \| `t2t` (required) |
| `-s, --source` | source key, default `refseq` |
| `-o, --output` | output path, or `-` for stdout |
| `--annotation-file` / `--annotation-url` | use your own annotation |
| `--format` | force `gtf`/`gff3`/`genepred`/`bed` |
| `--all-biotypes` | don't prefer protein-coding when genes overlap |
| `--join` | separator for multiple genes (default `;`) |
| `--none-label` | label for no-overlap regions (default `.`) |
| `--refresh` | re-download the annotation |
| `--cache-dir` | override cache location |
| `--no-banner` / `--no-color` / `-q` | quieter output |

## Caching

Downloads are cached (default `~/.cache/bedboy`, or `$BEDBOY_CACHE`).

```bash
bedboy cache --path     # show cache dir + contents
bedboy cache --clear    # wipe it
```

## How overlap & gene choice work

- Coordinates are normalised to **0-based half-open** internally; UCSC genePred
  is already 0-based, GTF/GFF (1-based inclusive) is converted.
- Chromosome names are harmonised, so `chr1` ↔ `1` and `chrM` ↔ `chrMT` match.
- A target is assigned every gene whose **gene body** overlaps it. When several
  overlap and biotype info is available, protein-coding symbols win unless you
  pass `--all-biotypes`.

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
pip install -e ".[dev]"
pytest
ruff check .
```

## Notes & caveats

- Gene-body annotation: an intronic target still gets its host gene's name
  (what you usually want for panel/target labelling).
- T2T sources depend on UCSC `hs1` table availability; if a table moves, use
  `--annotation-url`/`--annotation-file`. `bedboy sources -g t2t` prints the URL.
- Symbols reflect the chosen release, so very recently renamed genes may differ
  from the latest HGNC nomenclature.

## License

MIT — see [LICENSE](LICENSE).

<div align="center"><sub>⌐■-■ stay bad.</sub></div>
