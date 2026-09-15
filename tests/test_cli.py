"""CLI contracts: clean streams, visible errors and preserved files."""

import gzip
from pathlib import Path

import pytest
from click.testing import CliRunner

from bedboy.cli import main

DATA = Path(__file__).parent / "data"
ANNOTATION = str(DATA / "mini.genes.bed")


def run(*args, **kwargs):
    return CliRunner().invoke(main, list(args), **kwargs)


def annotate(path, *args, **kwargs):
    return run(
        "annotate", str(path), "-g", "hg38", "--annotation-file", ANNOTATION, *args, **kwargs
    )


def test_stdout_contains_only_bed():
    result = annotate(DATA / "mini_input.bed", "-o", "-", "--no-color")
    assert result.exit_code == 0, result.output
    assert result.stdout == "chr1\t1600\t1700\tAAA\nchr2\t5500\t5600\tCCC\nchr3\t10\t20\t.\n"
    assert "BedBoy" in result.stderr
    assert "\x1b" not in result.output


def test_stdin_defaults_to_stdout_and_quiet_suppresses_diagnostics():
    result = annotate("-", "-q", input="chr1 1600 1700\n")
    assert result.exit_code == 0, result.output
    assert result.stdout == "chr1\t1600\t1700\tAAA\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    "command",
    [
        ["sources", "-g", "unknown"],
        ["annotate", "-", "-g", "unknown", "-q"],
    ],
)
def test_invalid_genome_is_a_visible_click_error(command):
    result = run(*command)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Unknown genome" in result.stderr
    assert "Traceback" not in result.output


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_output_cannot_overwrite_input(tmp_path, alias):
    path = tmp_path / "input.bed"
    original = "chr1\t1600\t1700\n"
    path.write_text(original)
    output = path
    if alias != "same":
        output = tmp_path / "alias.bed"
        if alias == "symlink":
            output.symlink_to(path)
        else:
            output.hardlink_to(path)
    result = annotate(path, "-o", str(output), "-q")
    assert result.exit_code == 1
    assert "output must be different" in result.stderr
    assert path.read_text() == original


def test_output_cannot_overwrite_annotation(tmp_path):
    annotation = tmp_path / "genes.bed"
    annotation.write_text("chr1\t1000\t2000\tAAA\n")
    result = run(
        "annotate",
        str(DATA / "mini_input.bed"),
        "-g",
        "hg38",
        "--annotation-file",
        str(annotation),
        "-o",
        str(annotation),
        "-q",
    )
    assert result.exit_code == 1
    assert annotation.read_text() == "chr1\t1000\t2000\tAAA\n"


def test_failed_strict_run_preserves_previous_output(tmp_path):
    path = tmp_path / "input.bed"
    path.write_text("chr1\t1600\t1700\nchr1\t-1\t30\n")
    output = tmp_path / "output.bed"
    output.write_text("previous result\n")
    result = annotate(path, "-o", str(output), "--strict", "-q")
    assert result.exit_code == 1
    assert "line 2" in result.stderr
    assert output.read_text() == "previous result\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["input.bed", "output.bed"]


def test_malformed_records_warn_and_pass_through(tmp_path):
    path = tmp_path / "input.bed"
    path.write_text("chr1\t-1\t30\n")
    result = annotate(path, "-o", "-", "--no-banner")
    assert result.exit_code == 0
    assert result.stdout == path.read_text()
    assert "1 malformed BED record" in result.stderr


def test_gzip_input_default_output_and_gzip_output(tmp_path):
    path = tmp_path / "input.bed.gz"
    with gzip.open(path, "wt") as handle:
        handle.write("chr1\t1600\t1700\n")
    result = annotate(path, "-q")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "input.bedboy.bed").read_text() == "chr1\t1600\t1700\tAAA\n"
    output = tmp_path / "output.bed.gz"
    result = annotate(path, "-q", "-o", str(output))
    assert result.exit_code == 0, result.output
    with gzip.open(output, "rt") as handle:
        assert handle.read() == "chr1\t1600\t1700\tAAA\n"


def test_conflicting_annotation_options_are_rejected():
    result = annotate("-", "--annotation-url", "https://example.org/genes.gtf", "-q")
    assert result.exit_code == 2
    assert "mutually exclusive" in result.stderr


@pytest.mark.parametrize("option", ["--join", "--none-label"])
def test_labels_cannot_inject_columns(option):
    result = annotate("-", option, "bad\tvalue", "-q")
    assert result.exit_code == 2
    assert "must not contain tabs or newlines" in result.stderr


def test_read_write_errors_have_no_traceback(tmp_path):
    result = annotate(DATA / "mini_input.bed", "-q", "-o", str(tmp_path / "missing" / "out.bed"))
    assert result.exit_code == 1
    assert "could not annotate BED" in result.stderr
    assert "Traceback" not in result.output


def test_empty_annotation_error_is_visible_when_quiet(tmp_path):
    annotation = tmp_path / "empty.gtf"
    annotation.touch()
    result = run("annotate", "-", "-g", "hg38", "--annotation-file", str(annotation), "-q")
    assert result.exit_code == 1
    assert "no genes parsed" in result.stderr


def test_sources_are_on_stdout():
    result = run("sources", "-g", "hs1", "--no-color", env={"COLUMNS": "240"})
    assert result.exit_code == 0
    assert "hs1.ncbiRefSeq.gp.gz" in result.stdout
    assert result.stderr == ""


def test_cache_path_and_clear_only_owned_files(tmp_path):
    owned = tmp_path / "0123456789__genes.gtf"
    owned.write_text("annotation")
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("user data")
    partial = tmp_path / ".0123456789__genes.gtf.random.part"
    partial.write_text("in progress")
    result = run("cache", "--path", "--cache-dir", str(tmp_path))
    assert result.exit_code == 0
    assert result.stdout == f"{tmp_path}\n"
    result = run("cache", "--clear", "--cache-dir", str(tmp_path))
    assert result.exit_code == 0
    assert not owned.exists()
    assert unrelated.read_text() == "user data"
    assert partial.read_text() == "in progress"


def test_markup_in_paths_and_labels_is_literal(tmp_path):
    path = tmp_path / "[red]input.bed"
    path.write_text("chr3\t10\t20\n")
    result = annotate(path, "--none-label", "[missing]", "--no-color", env={"COLUMNS": "240"})
    assert result.exit_code == 0, result.output
    assert "[red]input.bedboy.bed" in result.stderr
    assert "[missing]" in result.stderr


def test_builtin_download_path_and_quiet_download_error(monkeypatch):
    from bedboy.download import DownloadError

    monkeypatch.setattr("bedboy.cli.fetch", lambda *args, **kwargs: DATA / "mini.genepred")
    result = run("annotate", str(DATA / "mini_input.bed"), "-g", "hg38", "-o", "-", "-q")
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0].endswith("\tAAA")
    assert result.stderr == ""

    def fail(*args, **kwargs):
        raise DownloadError("connection failed")

    monkeypatch.setattr("bedboy.cli.fetch", fail)
    result = run("annotate", "-", "-g", "hg38", "-q")
    assert result.exit_code == 1
    assert "connection failed" in result.stderr
    assert result.stdout == ""


def test_custom_url_is_sniffed(monkeypatch):
    monkeypatch.setattr("bedboy.cli.fetch", lambda *args, **kwargs: DATA / "mini.genes.bed")
    result = run(
        "annotate",
        "-",
        "-g",
        "hg38",
        "--annotation-url",
        "https://example.org/genes",
        "-q",
        input="chr1\t1600\t1700\n",
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == "chr1\t1600\t1700\tAAA\n"


def test_corrupt_gzip_fails_without_publishing_output(tmp_path):
    path = tmp_path / "broken.bed.gz"
    path.write_bytes(gzip.compress(b"chr1\t1600\t1700\n")[:-8])
    result = annotate(path, "-q")
    assert result.exit_code == 1
    assert "could not annotate BED" in result.stderr
    assert not (tmp_path / "broken.bedboy.bed").exists()
    assert list(tmp_path.iterdir()) == [path]


def test_no_color_environment_applies_to_mascot():
    result = run(env={"NO_COLOR": "1", "FORCE_COLOR": "1"})
    assert result.exit_code == 0
    assert "B E D  B O Y" in result.stderr
    assert "\x1b" not in result.stderr
