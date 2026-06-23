"""BedBoy — annotate BED intervals with gene names.

A fast, colorful command-line tool that takes an unannotated BED file and a
genome build (hg19 / hg38 / t2t) and writes a BED file with a gene-name column.
"""

__version__ = "1.0.0"
__author__ = "BedBoy contributors"
__license__ = "MIT"

from .annotate import GeneIndex, annotate_stream, build_index_from_file
from .sources import list_sources, resolve_source, sources_for
from .utils import Gene

__all__ = [
    "__version__",
    "Gene",
    "GeneIndex",
    "annotate_stream",
    "build_index_from_file",
    "list_sources",
    "resolve_source",
    "sources_for",
]
