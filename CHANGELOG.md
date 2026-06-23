# Changelog

All notable changes to BedBoy are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and BedBoy adheres to
semantic versioning.

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
