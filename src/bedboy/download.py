"""Download and cache annotation files."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TransferSpeedColumn,
)


def cache_dir(override: str | None = None) -> Path:
    if override:
        d = Path(override).expanduser()
    elif os.environ.get("BEDBOY_CACHE"):
        d = Path(os.environ["BEDBOY_CACHE"]).expanduser()
    else:
        base = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
        d = Path(base) / "bedboy"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_name(url: str) -> str:
    h = hashlib.sha1(url.encode()).hexdigest()[:10]
    tail = url.split("/")[-1] or "annotation"
    return f"{h}__{tail}"


def fetch(
    url: str,
    *,
    console: Console,
    cache: str | None = None,
    force: bool = False,
    timeout: int = 60,
) -> Path:
    """Return a local path to ``url``'s contents, downloading + caching if needed."""
    target = cache_dir(cache) / _cache_name(url)
    if target.exists() and target.stat().st_size > 0 and not force:
        console.print(f"[bb.muted]cache hit:[/bb.muted] [bb.path]{target}[/bb.path]")
        return target

    tmp = target.with_suffix(target.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            if r.status_code != 200:
                raise DownloadError(
                    f"server returned HTTP {r.status_code} for {url}"
                )
            total = int(r.headers.get("Content-Length", 0)) or None
            with Progress(
                SpinnerColumn(),
                TextColumn("[bb.accent]downloading[/bb.accent] {task.fields[name]}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                console=console,
                transient=True,
            ) as prog:
                task = prog.add_task("dl", total=total, name=url.split("/")[-1])
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        if chunk:
                            fh.write(chunk)
                            prog.advance(task, len(chunk))
    except requests.RequestException as e:  # network-level failure
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise DownloadError(f"could not download {url}: {e}") from e

    tmp.replace(target)
    console.print(f"[bb.ok]cached[/bb.ok] [bb.path]{target}[/bb.path]")
    return target


class DownloadError(RuntimeError):
    """Raised when an annotation file cannot be retrieved."""
