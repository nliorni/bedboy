"""Built-in annotation source registry.

Design notes
------------
We centre the defaults on UCSC ``goldenPath`` *genePred* tables
(``ncbiRefSeq`` / ``refGene``) because they:

* exist uniformly for **hg19**, **hg38** and **hs1** (T2T-CHM13v2.0),
* use ``chr``-prefixed sequence names that line up with most BED files,
* carry the gene symbol in a single column (``name2``), and
* parse identically across builds.

GENCODE GTFs (EBI) are offered as an alternative for hg19/hg38. Every source
can be overridden at run time with ``--annotation-url`` or ``--annotation-file``,
so the registry is a convenience, not a hard dependency.
"""
from __future__ import annotations

from dataclasses import dataclass

UCSC = "https://hgdownload.soe.ucsc.edu/goldenPath/{db}/database/{table}.txt.gz"
# bigZips genePred dumps (used for hs1/T2T, which has no database/ table mirror).
UCSC_GP = "https://hgdownload.soe.ucsc.edu/goldenPath/{db}/bigZips/genes/{file}.gp.gz"
GENCODE = "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/{rel}"

# Pinned GENCODE release (EBI keeps historical releases, so this stays valid).
# Bump this single constant to follow new GENCODE releases.
_GC_REL = "release_50"
_GC_VER = "50"

# Canonical genome key -> UCSC assembly db name.
GENOME_DB = {"hg19": "hg19", "hg38": "hg38", "t2t": "hs1"}

# Accepted aliases -> canonical key.
GENOME_ALIASES = {
    "hg19": "hg19", "grch37": "hg19", "b37": "hg19",
    "hg38": "hg38", "grch38": "hg38", "b38": "hg38",
    "t2t": "t2t", "chm13": "t2t", "hs1": "t2t", "chm13v2": "t2t", "chm13v2.0": "t2t",
}

DEFAULT_SOURCE = "refseq"


@dataclass(frozen=True, slots=True)
class Source:
    genome: str
    key: str
    label: str
    url: str
    fmt: str          # gtf | gff3 | genepred | bed
    note: str = ""


def _ucsc(db: str, table: str) -> str:
    return UCSC.format(db=db, table=table)


# (genome, source key) -> Source
_REGISTRY: dict[str, dict[str, Source]] = {
    "hg19": {
        "refseq": Source("hg19", "refseq", "RefSeq (UCSC ncbiRefSeq)",
                         _ucsc("hg19", "ncbiRefSeq"), "genepred"),
        "refgene": Source("hg19", "refgene", "RefSeq curated (UCSC refGene)",
                          _ucsc("hg19", "refGene"), "genepred"),
        "gencode": Source("hg19", "gencode", f"GENCODE v{_GC_VER} (lift37, basic)",
                          f"{GENCODE.format(rel=_GC_REL)}/GRCh37_mapping/"
                          f"gencode.v{_GC_VER}lift37.basic.annotation.gtf.gz", "gtf"),
    },
    "hg38": {
        "refseq": Source("hg38", "refseq", "RefSeq (UCSC ncbiRefSeq)",
                         _ucsc("hg38", "ncbiRefSeq"), "genepred"),
        "refgene": Source("hg38", "refgene", "RefSeq curated (UCSC refGene)",
                          _ucsc("hg38", "refGene"), "genepred"),
        "gencode": Source("hg38", "gencode", f"GENCODE v{_GC_VER} (basic)",
                          f"{GENCODE.format(rel=_GC_REL)}/"
                          f"gencode.v{_GC_VER}.basic.annotation.gtf.gz", "gtf"),
    },
    "t2t": {
        "refseq": Source("t2t", "refseq", "RefSeq on CHM13v2.0 (UCSC hs1 ncbiRefSeq)",
                         UCSC_GP.format(db="hs1", file="hs1.ncbiRefSeq"), "genepred",
                         note="T2T-CHM13v2.0 (UCSC hs1). If unavailable, try "
                              "--source catliftoff or supply --annotation-url."),
        "catliftoff": Source("t2t", "catliftoff", "CAT/Liftoff gene set (UCSC hs1 catLiftOffGenesV1)",
                             UCSC_GP.format(db="hs1", file="hs1.catLiftOffGenesV1"), "genepred",
                             note="CHM13v2.0 CAT + Liftoff gene set."),
    },
}


def canonical_genome(genome: str) -> str:
    key = GENOME_ALIASES.get(genome.strip().lower())
    if key is None:
        raise KeyError(
            f"Unknown genome '{genome}'. Choose one of: hg19, hg38, t2t "
            f"(aliases: grch37, grch38, chm13/hs1)."
        )
    return key


def resolve_source(genome: str, source: str) -> Source:
    g = canonical_genome(genome)
    table = _REGISTRY[g]
    key = source.strip().lower()
    if key not in table:
        raise KeyError(
            f"Source '{source}' is not available for {g}. "
            f"Available: {', '.join(table)}."
        )
    return table[key]


def sources_for(genome: str) -> dict[str, Source]:
    return dict(_REGISTRY[canonical_genome(genome)])


def list_sources() -> dict[str, dict[str, Source]]:
    return {g: dict(s) for g, s in _REGISTRY.items()}
