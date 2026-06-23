"""The overlap engine and the streaming BED annotator."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
from ncls import NCLS

from .parsers import parse
from .utils import Gene, normalize_chrom, open_text


@dataclass
class GeneIndex:
    """Per-chromosome nested-containment index for fast overlap queries."""

    _ncls: dict = field(default_factory=dict)
    _names: dict = field(default_factory=dict)
    _coding: dict = field(default_factory=dict)
    n_genes: int = 0

    @classmethod
    def build(cls, genes: Iterable[Gene]) -> "GeneIndex":
        buckets: dict[str, list[Gene]] = {}
        for g in genes:
            if g.end > g.start:
                buckets.setdefault(g.chrom, []).append(g)

        idx = cls()
        for chrom, gl in buckets.items():
            starts = np.fromiter((g.start for g in gl), dtype=np.int64, count=len(gl))
            ends = np.fromiter((g.end for g in gl), dtype=np.int64, count=len(gl))
            ids = np.arange(len(gl), dtype=np.int64)
            idx._ncls[chrom] = NCLS(starts, ends, ids)
            idx._names[chrom] = np.array([g.name for g in gl], dtype=object)
            idx._coding[chrom] = np.fromiter(
                (g.biotype == "protein_coding" for g in gl), dtype=bool, count=len(gl)
            )
            idx.n_genes += len(gl)
        return idx

    def query(
        self,
        chrom: str,
        start: int,
        end: int,
        *,
        prefer_coding: bool = True,
    ) -> list[str]:
        """Return sorted, unique overlapping gene symbols for an interval."""
        key = normalize_chrom(chrom)
        nc = self._ncls.get(key)
        if nc is None:
            return []
        hit_ids = [h[2] for h in nc.find_overlap(start, end)]
        if not hit_ids:
            return []
        names = self._names[key]
        coding = self._coding[key]
        if prefer_coding and coding[hit_ids].any():
            chosen = {names[i] for i in hit_ids if coding[i]}
        else:
            chosen = {names[i] for i in hit_ids}
        return sorted(chosen)


@dataclass
class Stats:
    total: int = 0
    annotated: int = 0
    multi: int = 0
    unannotated: int = 0
    passthrough: int = 0

    @property
    def pct_annotated(self) -> float:
        return 100.0 * self.annotated / self.total if self.total else 0.0


def build_index_from_file(path: str, fmt: str) -> GeneIndex:
    return GeneIndex.build(parse(path, fmt))


def annotate_stream(
    index: GeneIndex,
    in_bed: str,
    out_handle,
    *,
    prefer_coding: bool = True,
    join: str = ";",
    none_label: str = ".",
    progress_cb=None,
) -> Stats:
    """Stream ``in_bed`` and append a gene-name column to each record.

    A 3-column BED therefore gains the gene name as column 4; files that already
    carry extra columns get the gene name appended as a new trailing column.
    """
    st = Stats()
    with open_text(in_bed) as fin:
        for line in fin:
            if not line.strip() or line.startswith(("#", "track", "browser")):
                out_handle.write(line if line.endswith("\n") else line + "\n")
                st.passthrough += 1
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 3:
                out_handle.write(line if line.endswith("\n") else line + "\n")
                st.passthrough += 1
                continue
            st.total += 1
            try:
                start, end = int(f[1]), int(f[2])
            except ValueError:
                out_handle.write(line if line.endswith("\n") else line + "\n")
                st.passthrough += 1
                st.total -= 1
                continue
            genes = index.query(f[0], start, end, prefer_coding=prefer_coding)
            if genes:
                st.annotated += 1
                if len(genes) > 1:
                    st.multi += 1
                value = join.join(genes)
            else:
                st.unannotated += 1
                value = none_label
            out_handle.write("\t".join([*f, value]) + "\n")
            if progress_cb is not None:
                progress_cb()
    return st
