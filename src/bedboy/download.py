"""Download and cache annotation files."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests
from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TransferSpeedColumn,
)


class DownloadError(RuntimeError):
    """Raised when an annotation file cannot be retrieved."""


def cache_dir(override: str | None = None) -> Path:
    if override:
        d = Path(override).expanduser()
    elif os.environ.get("BEDBOY_CACHE"):
        d = Path(os.environ["BEDBOY_CACHE"]).expanduser()
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
        d = Path(base).expanduser() / "bedboy"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_name(url: str) -> str:
    h = hashlib.sha1(url.encode()).hexdigest()[:10]
    # Keep the format suffix, but never include URL queries, slashes or fragments.
    tail = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    tail = re.sub(r"[^A-Za-z0-9._-]", "_", tail)[-180:]
    tail = tail if tail.strip(".") else "annotation"
    return f"{h}__{tail}"


def cached_files(path: Path) -> list[Path]:
    """Only completed files owned by BedBoy; leave unrelated files alone."""
    return sorted(
        p
        for p in path.iterdir()
        if re.fullmatch(r"[0-9a-f]{10}__.+", p.name)
        and not p.name.endswith(".part")
        and p.is_file()
    )


def fetch(
    url: str,
    *,
    console: Console,
    cache: str | None = None,
    force: bool = False,
    timeout: int = 60,
) -> Path:
    """Download atomically; a failed refresh preserves the last cached file."""
    tmp = None
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise DownloadError("annotation URL must use http:// or https://")
        target = cache_dir(cache) / _cache_name(url)
        if target.is_file() and target.stat().st_size > 0 and not force:
            console.print(
                f"[bb.muted]cache hit:[/bb.muted] [bb.path]{escape(str(target))}[/bb.path]"
            )
            return target

        with requests.get(url, stream=True, timeout=timeout) as response:
            if response.status_code != 200:
                raise DownloadError(f"server returned HTTP {response.status_code} for {url}")
            if "text/html" in response.headers.get("Content-Type", "").lower():
                raise DownloadError(
                    f"server returned an HTML page instead of annotation data: {url}"
                )
            length = response.headers.get("Content-Length", "")
            total = int(length) if length.isdigit() and int(length) > 0 else None
            received = 0
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".part",
                delete=False,
            ) as fh:
                tmp = Path(fh.name)
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bb.accent]downloading annotation[/bb.accent]"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    console=console,
                    transient=True,
                    disable=console.quiet or not console.is_terminal,
                ) as prog:
                    task = prog.add_task("download", total=total)
                    for chunk in response.iter_content(chunk_size=1 << 16):
                        if chunk:
                            fh.write(chunk)
                            received += len(chunk)
                            prog.advance(task, len(chunk))
            if received == 0:
                raise DownloadError(f"server returned an empty annotation: {url}")
            # Requests decodes HTTP transfer compression; lengths then differ.
            if total and not response.headers.get("Content-Encoding") and received != total:
                raise DownloadError(
                    f"incomplete annotation download: expected {total}, got {received} bytes"
                )
        tmp.replace(target)
        console.print(f"[bb.ok]cached[/bb.ok] [bb.path]{escape(str(target))}[/bb.path]")
        return target
    except (requests.RequestException, OSError, ValueError) as exc:
        raise DownloadError(f"could not download {url}: {exc}") from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
