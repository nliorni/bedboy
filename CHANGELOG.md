# Changelog

All notable changes to BedBoy are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and BedBoy adheres to
semantic versioning.

## [Unreleased]

### Changed
- Replaced the old mascot with a boy who never leaves bed: a starry quilt,
  moonlit terminal colors, a new SVG README banner, and “gene names, without
  leaving bed” branding.
- Annotation diagnostics now use stderr, leaving stdout suitable for BED pipelines.
- `cache --path` prints only the path; `cache --clear` removes completed BedBoy
  downloads while preserving unrelated files and active temporary downloads.
- Package author metadata now identifies nliorni.

### Added
- BED input from stdin (`-`), whitespace-delimited BED, and gzip file output.
- `--strict` for line-numbered malformed BED errors, plus invalid-row counts
  and warnings in the default permissive mode.
- Regression tests for coordinate boundaries, parser formats, CLI streams,
  output protection, cache failures, and concurrent downloads.
- Wheel build/install smoke tests in CI, including Python 3.13.

### Fixed
- Plain output now suppresses all ANSI styling even when `FORCE_COLOR` or
  `TTY_COMPATIBLE` is set; color tests explicitly cover different terminal types.
- Replaced the broken T2T CAT/Liftoff genePred URL with the assembly hub GFF3.
- Quiet mode no longer hides errors; invalid sources and I/O failures produce
  readable errors instead of tracebacks.
- Prevented input/annotation overwrite, including symlink and hard-link aliases;
  failed runs preserve previous file output.
- Normalized chromosomes in the public `GeneIndex.build` API and validated
  coordinate bounds before passing values to the native overlap engine.
- Empty intervals no longer produce spurious overlaps.
- Basic 10-column genePred support; BED12 and single-attribute GFF3 detection.
- Mixed GTF annotations retain fallback genes and IDs shared across chromosomes.
- GFF3 attribute decoding, gene biotypes, and embedded FASTA handling.
- URL-safe cache names, unique temporary downloads, empty/HTML/truncated response
  detection, and cleanup that preserves a cached copy on failed refresh.
- Corrected README badge links, source paths, and input/output documentation.

## [1.0.0] - 2026-06-23
### Added
- `bedboy annotate` — append a gene-name column to any BED file.
- Genome builds: **hg19**, **hg38**, **t2t** (aliases: grch37/grch38/chm13/hs1).
- Built-in sources: UCSC `ncbiRefSeq` (default) and `refGene` genePred tables,
  GENCODE GTF (hg19/hg38), and CAT/Liftoff for T2T.
- Automatic download + on-disk caching of annotation files.
- Parsers for genePred, GTF, GFF3 and gene-BED, with auto format detection.
- Fast NCLS-based interval overlap with protein-coding preference.
- Colourful Rich CLI: mascot, progress bars and a summary report.
- `bedboy sources` and `bedboy cache` helper commands.
