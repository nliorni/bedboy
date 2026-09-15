"""Network-free tests for cache reuse, failed refreshes and concurrent writers."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import MagicMock

import pytest
import requests

from bedboy.console import make_console
from bedboy.download import DownloadError, _cache_name, cache_dir, fetch

URL = "https://example.org/genes.gtf.gz?release=50#download"


def response(chunks=(b"genes",), status=200, headers=None):
    result = MagicMock()
    result.__enter__.return_value = result
    result.status_code = status
    result.headers = headers or {}
    result.iter_content.return_value = iter(chunks)
    return result


def download(tmp_path, **kwargs):
    return fetch(URL, console=make_console(quiet=True), cache=str(tmp_path), **kwargs)


def test_cache_names_preserve_suffix_and_ignore_query_path():
    name = _cache_name(URL)
    assert name.endswith("__genes.gtf.gz")
    assert "?" not in name and "#" not in name
    assert _cache_name(URL + "2") != name
    assert "/" not in _cache_name("https://example.org/%2f..%2fgenes.gtf")


def test_reuse_and_refresh(tmp_path, monkeypatch):
    get = MagicMock(return_value=response())
    monkeypatch.setattr(requests, "get", get)
    path = download(tmp_path)
    assert path.read_bytes() == b"genes"
    assert download(tmp_path) == path
    assert get.call_count == 1
    get.return_value = response((b"new",))
    assert download(tmp_path, force=True).read_bytes() == b"new"
    assert get.call_count == 2
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("failure", ["network", "http", "empty", "html", "truncated", "write"])
def test_failed_refresh_preserves_cache_and_cleans_temp(tmp_path, monkeypatch, failure):
    path = tmp_path / _cache_name(URL)
    path.write_bytes(b"old")
    result = response()
    if failure == "network":
        result.iter_content.side_effect = requests.ConnectionError("disconnected")
    elif failure == "http":
        result.status_code = 404
    elif failure == "empty":
        result.iter_content.return_value = iter(())
    elif failure == "html":
        result.headers = {"Content-Type": "text/html; charset=utf-8"}
    elif failure == "truncated":
        result.headers = {"Content-Length": "100"}
    elif failure == "write":
        result.iter_content.side_effect = OSError("disk full")
    monkeypatch.setattr(requests, "get", MagicMock(return_value=result))
    with pytest.raises(DownloadError):
        download(tmp_path, force=True)
    assert path.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [path]


def test_partly_received_response_is_cleaned_up(tmp_path, monkeypatch):
    def chunks():
        yield b"partial"
        raise requests.ConnectionError("interrupted")

    result = response()
    result.iter_content.return_value = chunks()
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: result)
    with pytest.raises(DownloadError):
        download(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Length": "unknown"},
        {"Content-Length": "1", "Content-Encoding": "gzip"},
    ],
)
def test_unusable_transfer_size_does_not_reject_valid_data(tmp_path, monkeypatch, headers):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response(headers=headers))
    assert download(tmp_path).read_bytes() == b"genes"


def test_concurrent_downloads_publish_complete_files(tmp_path, monkeypatch):
    barrier = Barrier(2)

    def get(*args, **kwargs):
        result = response()

        def chunks():
            yield b"begin"
            barrier.wait(timeout=5)
            yield b"end"

        result.iter_content.return_value = chunks()
        return result

    monkeypatch.setattr(requests, "get", get)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(download, tmp_path, force=True) for _ in range(2)]
        paths = [f.result(timeout=10) for f in futures]
    assert paths[0] == paths[1]
    assert paths[0].read_bytes() == b"beginend"
    assert list(tmp_path.iterdir()) == [paths[0]]


def test_cache_environment_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("BEDBOY_CACHE", raising=False)
    assert cache_dir() == tmp_path / "xdg" / "bedboy"
    monkeypatch.setenv("BEDBOY_CACHE", str(tmp_path / "env"))
    assert cache_dir() == tmp_path / "env"
    assert cache_dir(str(tmp_path / "override")) == tmp_path / "override"
