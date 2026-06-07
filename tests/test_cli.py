from pathlib import Path

from markitdown_plus.cli import main


def test_clean_command(tmp_path: Path):
    input_file = tmp_path / "dirty.md"
    output_file = tmp_path / "clean.md"
    input_file.write_text("#Title\n\n(cid:123)\n\nHello\nworld.", encoding="utf-8")

    exit_code = main(["clean", str(input_file), "--output", str(output_file)])

    assert exit_code == 0
    assert output_file.exists()
    assert "# Title" in output_file.read_text(encoding="utf-8")


def test_clean_command_rejects_directory_output(tmp_path: Path):
    input_file = tmp_path / "dirty.md"
    input_file.write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    exit_code = main(["clean", str(input_file), "--output", str(output_dir)])

    assert exit_code == 2


def test_chunk_command(tmp_path: Path):
    input_file = tmp_path / "clean.md"
    output_file = tmp_path / "chunks.jsonl"
    input_file.write_text("# Title\n\nHello world.", encoding="utf-8")

    exit_code = main(["chunk", str(input_file), "--output", str(output_file), "--chunk-size", "200"])

    assert exit_code == 0
    assert output_file.exists()


def test_convert_dry_run_lists_files(tmp_path: Path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "out"

    exit_code = main(["convert", str(docs), "--output", str(out), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Found: 1 file(s)" in captured.out
    assert "a.txt" in captured.out


def test_chunk_command_with_strategy(tmp_path: Path):
    input_file = tmp_path / "clean.md"
    output_file = tmp_path / "chunks.jsonl"
    input_file.write_text("# Title\n\nHello world.", encoding="utf-8")

    exit_code = main([
        "chunk",
        str(input_file),
        "--output",
        str(output_file),
        "--chunk-size",
        "200",
        "--chunk-strategy",
        "fixed",
    ])

    assert exit_code == 0
    assert '"strategy": "fixed"' in output_file.read_text(encoding="utf-8")


def test_convert_dry_run_accepts_workers_and_extract_assets(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "out"

    exit_code = main([
        "convert",
        str(docs),
        "--output",
        str(out),
        "--dry-run",
        "--workers",
        "0",
        "--extract-assets",
        "--chunk-strategy",
        "semantic-lite",
    ])

    assert exit_code == 0


def test_verbose_error_prints_traceback(tmp_path: Path, capsys):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    exit_code = main(["clean", "missing.md", "--output", str(output_dir / "x.md"), "--verbose"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Traceback" in captured.err
