import json
from pathlib import Path

from markitdown_plus.manifest import Manifest, write_manifest


def test_manifest_add_success_increments_without_recount():
    manifest = Manifest(source="docs", output="out")
    manifest.add_success("a.pdf", "a.md")
    manifest.add_success("b.pdf", "b.md", metadata_path="b.json")

    assert manifest.total == 2
    assert manifest.success == 2
    assert manifest.failed == 0


def test_manifest_add_failed_and_failed_records():
    manifest = Manifest()
    manifest.add_success("a.pdf", "a.md")
    manifest.add_failed("b.pdf", "boom")

    failed = manifest.failed_records()
    assert len(failed) == 1
    assert failed[0]["source_path"] == "b.pdf"
    assert failed[0]["error"] == "boom"


def test_manifest_to_dict_omits_none_fields():
    manifest = Manifest()
    manifest.add_success("a.pdf", "a.md")
    record = manifest.to_dict()["files"][0]
    assert "chunks_path" not in record
    assert "error" not in record


def test_write_manifest_with_and_without_failures(tmp_path: Path):
    manifest = Manifest()
    manifest.add_failed("bad.pdf", "boom")
    manifest_path, failed_path = write_manifest(manifest, tmp_path)
    assert manifest_path.exists()
    assert failed_path is not None and failed_path.exists()

    manifest2 = Manifest()
    manifest2.add_success("good.pdf", "good.md")
    manifest_path, failed_path = write_manifest(manifest2, tmp_path)
    assert manifest_path.exists()
    assert failed_path is None
    assert not (tmp_path / "failed.json").exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["success"] == 1
