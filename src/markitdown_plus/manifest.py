"""Batch conversion manifest support."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .__about__ import __version__


def _drop_none(value: Any) -> Any:
    """Recursively remove None values from dictionaries/lists for cleaner JSON."""
    if isinstance(value, dict):
        return {k: _drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


@dataclass
class ManifestRecord:
    """One file record inside a conversion manifest."""

    source_path: str
    status: str
    output_path: str | None = None
    chunks_path: str | None = None
    metadata_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly record without meaningless null fields."""
        return _drop_none(asdict(self))

    def to_json(self) -> str:
        """Serialize this record as one JSONL row."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class Manifest:
    """A conversion run manifest.

    For very large folders, callers may disable in-memory record storage and
    stream each record to `manifest-records.jsonl`. The summary counters still
    stay in memory, while the heavy per-file data is kept on disk.
    """

    tool: str = "markitdown-plus"
    version: str = __version__
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = ""
    output: str = ""
    total: int = 0
    success: int = 0
    failed: int = 0
    files: list[ManifestRecord] = field(default_factory=list)
    files_truncated: bool = False
    records_path: str | None = None
    failed_records_path: str | None = None
    _store_records: bool = field(default=True, repr=False, compare=False)

    def enable_streaming(self, records_path: str | Path, failed_records_path: str | Path | None = None) -> None:
        """Store per-file records on disk instead of keeping them all in memory."""
        self._store_records = False
        self.files_truncated = True
        self.records_path = str(records_path)
        if failed_records_path is not None:
            self.failed_records_path = str(failed_records_path)

    def _add_record(self, record: ManifestRecord) -> ManifestRecord:
        if self._store_records:
            self.files.append(record)
        else:
            self.files_truncated = True

        self.total += 1
        if record.status == "success":
            self.success += 1
        elif record.status == "failed":
            self.failed += 1
        return record

    def add_success(
        self,
        source_path: str,
        output_path: str,
        chunks_path: str | None = None,
        metadata_path: str | None = None,
    ) -> ManifestRecord:
        return self._add_record(
            ManifestRecord(
                source_path=source_path,
                status="success",
                output_path=output_path,
                chunks_path=chunks_path,
                metadata_path=metadata_path,
            )
        )

    def add_failed(self, source_path: str, error: str) -> ManifestRecord:
        return self._add_record(ManifestRecord(source_path=source_path, status="failed", error=error))

    def _recount(self) -> None:
        """Recalculate counters when records are edited externally."""
        self.total = len(self.files)
        self.success = sum(1 for record in self.files if record.status == "success")
        self.failed = sum(1 for record in self.files if record.status == "failed")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "tool": self.tool,
            "version": self.version,
            "created_at": self.created_at,
            "source": self.source,
            "output": self.output,
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "files_truncated": self.files_truncated,
            "records_path": self.records_path,
            "failed_records_path": self.failed_records_path,
            "files": [record.to_dict() for record in self.files],
        }
        return _drop_none(payload)

    def failed_records(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self.files if record.status == "failed"]


def append_manifest_record(path: str | Path, record: ManifestRecord) -> Path:
    """Append one manifest record to a JSONL file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        f.write(record.to_json() + "\n")
    return output


def write_manifest(manifest: Manifest, output_dir: str | Path) -> tuple[Path, Path | None]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    failed_path: Path | None = None
    failed_records = manifest.failed_records()
    if manifest.failed and failed_records:
        failed_path = output / "failed.json"
        failed_path.write_text(
            json.dumps(failed_records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        old_failed_path = output / "failed.json"
        if old_failed_path.exists():
            old_failed_path.unlink()
    return manifest_path, failed_path
