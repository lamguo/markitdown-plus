import json
from pathlib import Path

import pytest
from markitdown_plus import batch
from markitdown_plus.batch import (
    BatchOptions,
    discover_files,
    parse_extensions,
    run_batch,
    validate_input_output_paths,
)


class FakeConverter:
    def __init__(self, enable_plugins: bool = False) -> None:
        self.enable_plugins = enable_plugins

    def convert_file(self, path: Path) -> str:
        if path.name == "bad.txt":
            raise RuntimeError("boom")
        return f"# Converted\n\n{path.name}\n"


def test_parse_extensions():
    assert parse_extensions("pdf,docx,.xlsx") == {".pdf", ".docx", ".xlsx"}
    assert parse_extensions(None) is None


def test_discover_files_filters_extensions(tmp_path: Path):
    (tmp_path / "a.pdf").write_text("pdf", encoding="utf-8")
    (tmp_path / "b.docx").write_text("docx", encoding="utf-8")
    (tmp_path / "c.exe").write_text("exe", encoding="utf-8")

    files = discover_files(tmp_path, extensions={".pdf", ".docx"})
    names = {file.name for file in files}

    assert names == {"a.pdf", "b.docx"}


def test_discover_files_excludes_markdown_by_default(tmp_path: Path):
    (tmp_path / "notes.md").write_text("# Notes", encoding="utf-8")
    assert discover_files(tmp_path) == []
    assert discover_files(tmp_path, extensions={".md"}) == [tmp_path / "notes.md"]


def test_discover_files_single_file(tmp_path: Path):
    source = tmp_path / "a.txt"
    source.write_text("hello", encoding="utf-8")
    assert discover_files(source) == [source]


def test_discover_files_recursive(tmp_path: Path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "a.pdf").write_text("pdf", encoding="utf-8")

    assert discover_files(tmp_path, recursive=False, extensions={".pdf"}) == []
    assert len(discover_files(tmp_path, recursive=True, extensions={".pdf"})) == 1


def test_validate_input_output_paths_rejects_same_path(tmp_path: Path):
    with pytest.raises(ValueError):
        validate_input_output_paths(tmp_path, tmp_path)


def test_validate_input_output_paths_rejects_output_inside_input(tmp_path: Path):
    input_dir = tmp_path / "docs"
    input_dir.mkdir()
    with pytest.raises(ValueError):
        validate_input_output_paths(input_dir, input_dir / "out")


def test_run_batch_basic_with_clean_rag_and_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "报告.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)

    manifest = run_batch(
        BatchOptions(
            input_path=docs,
            output_dir=out,
            clean=True,
            rag=True,
            max_tokens=200,
            overlap=2,
            checkpoint_interval=1,
        )
    )

    assert manifest.success == 1
    assert manifest.failed == 0
    assert (out / "markdown" / "报告.md").exists()
    assert (out / "chunks" / "报告.jsonl").exists()
    metadata_file = out / "metadata" / "报告.json"
    assert metadata_file.exists()
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["clean_enabled"] is True
    assert metadata["rag_enabled"] is True
    assert metadata["output_size_bytes"] > 0
    assert (out / "manifest.json").exists()


def test_run_batch_partial_failure_writes_failed_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "good.txt").write_text("hello", encoding="utf-8")
    (docs / "bad.txt").write_text("bad", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)

    manifest = run_batch(BatchOptions(input_path=docs, output_dir=out))

    assert manifest.success == 1
    assert manifest.failed == 1
    failed = json.loads((out / "failed.json").read_text(encoding="utf-8"))
    assert failed[0]["status"] == "failed"
    assert "boom" in failed[0]["error"]


def test_run_batch_dry_run_does_not_need_converter(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "out"

    manifest = run_batch(BatchOptions(input_path=docs, output_dir=out, dry_run=True))

    assert manifest.total == 1
    assert manifest.files[0].output_path == "DRY_RUN"
    assert (out / "manifest.json").exists()


def test_run_batch_streams_large_manifest_to_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello", encoding="utf-8")
    (docs / "b.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)

    manifest = run_batch(BatchOptions(input_path=docs, output_dir=out, manifest_memory_limit=0))

    assert manifest.success == 2
    assert manifest.files == []
    assert manifest.files_truncated is True
    records_path = out / "manifest-records.jsonl"
    assert records_path.exists()
    rows = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    payload = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert payload["files_truncated"] is True
    assert payload["records_path"].endswith("manifest-records.jsonl")


def test_run_batch_streams_failed_records_to_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.txt").write_text("bad", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)

    manifest = run_batch(BatchOptions(input_path=docs, output_dir=out, manifest_memory_limit=0))

    assert manifest.failed == 1
    failed_path = out / "failed.jsonl"
    assert failed_path.exists()
    row = json.loads(failed_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["status"] == "failed"
    assert "boom" in row["error"]


def test_run_batch_progress_fallback_in_ci(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)
    monkeypatch.setenv("CI", "true")

    run_batch(BatchOptions(input_path=docs, output_dir=out, show_progress=True))

    captured = capsys.readouterr()
    assert "[1/1] Converting:" in captured.err


def test_run_batch_parallel_workers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ["a.txt", "b.txt", "c.txt"]:
        (docs / name).write_text("hello", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)

    manifest = run_batch(BatchOptions(input_path=docs, output_dir=out, workers=2, checkpoint_interval=1))

    assert manifest.success == 3
    assert manifest.failed == 0
    assert len(list((out / "markdown").glob("*.md"))) == 3


def test_run_batch_with_extract_assets_docx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import zipfile

    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "deck.docx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("word/media/image1.png", b"img")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)

    manifest = run_batch(BatchOptions(input_path=docs, output_dir=out, extract_assets=True))

    assert manifest.success == 1
    markdown = (out / "markdown" / "deck.md").read_text(encoding="utf-8")
    assert "Extracted Assets" in markdown
    assert (out / "assets" / "deck_img_001.png").exists()
    metadata = json.loads((out / "metadata" / "deck.json").read_text(encoding="utf-8"))
    assert metadata["extract_assets_enabled"] is True
    assert metadata["assets_count"] == 1


def test_run_batch_chunk_strategy_fixed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)

    run_batch(BatchOptions(input_path=docs, output_dir=out, rag=True, chunk_strategy="fixed", max_tokens=200))

    row = json.loads((out / "chunks" / "a.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["strategy"] == "fixed"


def test_run_batch_empty_directory(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    out = tmp_path / "out"

    manifest = run_batch(BatchOptions(input_path=docs, output_dir=out))

    assert manifest.total == 0
    assert manifest.success == 0
    assert (out / "manifest.json").exists()


def test_run_batch_fail_fast_stops_after_first_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.txt").write_text("bad", encoding="utf-8")
    (docs / "good.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr(batch, "PlusConverter", FakeConverter)

    manifest = run_batch(BatchOptions(input_path=docs, output_dir=out, continue_on_error=False))

    assert manifest.total == 1
    assert manifest.failed == 1
