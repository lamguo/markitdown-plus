"""Metadata helpers for converted documents."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .__about__ import __version__


@dataclass
class FileMetadata:
    """Basic conversion metadata for one source file."""

    source_path: str
    output_path: str
    file_name: str
    extension: str
    source_size_bytes: int
    output_size_bytes: int
    converted_at: str
    clean_enabled: bool = False
    rag_enabled: bool = False
    extract_assets_enabled: bool = False
    chunk_strategy: str = "heading"
    assets_count: int = 0
    assets: list[dict[str, Any]] = field(default_factory=list)
    conversion_time_seconds: float = 0.0
    markitdown_plus_version: str = __version__
    markitdown_version: str | None = None

    @property
    def size_bytes(self) -> int:
        """Backward-compatible alias for v0.1.0 metadata tests/users."""
        return self.source_size_bytes

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if payload.get("markitdown_version") is None:
            payload.pop("markitdown_version", None)
        if not payload.get("assets"):
            payload.pop("assets", None)
        return payload


def _markitdown_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("markitdown")
    except Exception:
        return None


def build_metadata(
    source_path: str | Path,
    output_path: str | Path,
    *,
    clean_enabled: bool = False,
    rag_enabled: bool = False,
    extract_assets_enabled: bool = False,
    chunk_strategy: str = "heading",
    assets: list[dict[str, Any]] | None = None,
    conversion_time_seconds: float = 0.0,
) -> FileMetadata:
    source = Path(source_path)
    output = Path(output_path)
    source_size = source.stat().st_size if source.exists() else 0
    output_size = output.stat().st_size if output.exists() else 0
    asset_list = assets or []
    return FileMetadata(
        source_path=str(source),
        output_path=str(output),
        file_name=source.name,
        extension=source.suffix.lower(),
        source_size_bytes=source_size,
        output_size_bytes=output_size,
        converted_at=datetime.now(timezone.utc).isoformat(),
        clean_enabled=clean_enabled,
        rag_enabled=rag_enabled,
        extract_assets_enabled=extract_assets_enabled,
        chunk_strategy=chunk_strategy,
        assets_count=len(asset_list),
        assets=asset_list,
        conversion_time_seconds=round(conversion_time_seconds, 6),
        markitdown_version=_markitdown_version(),
    )


def write_metadata(metadata: FileMetadata, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output
