import json
from pathlib import Path

from markitdown_plus.metadata import build_metadata, write_metadata


def test_build_metadata(tmp_path: Path):
    source = tmp_path / "report.pdf"
    source.write_text("hello", encoding="utf-8")
    output = tmp_path / "report.md"
    output.write_text("# Report", encoding="utf-8")

    metadata = build_metadata(source, output, clean_enabled=True, rag_enabled=True, conversion_time_seconds=1.23456)

    assert metadata.file_name == "report.pdf"
    assert metadata.extension == ".pdf"
    assert metadata.size_bytes > 0
    assert metadata.source_size_bytes > 0
    assert metadata.output_size_bytes > 0
    assert metadata.clean_enabled is True
    assert metadata.rag_enabled is True
    assert metadata.output_path.endswith("report.md")


def test_write_metadata(tmp_path: Path):
    source = tmp_path / "report.pdf"
    source.write_text("hello", encoding="utf-8")
    output = tmp_path / "report.md"
    output.write_text("# Report", encoding="utf-8")
    metadata = build_metadata(source, output)
    metadata_path = tmp_path / "metadata" / "report.json"

    write_metadata(metadata, metadata_path)

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["file_name"] == "report.pdf"
    assert "markitdown_plus_version" in payload
