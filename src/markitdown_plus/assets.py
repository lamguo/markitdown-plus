"""Asset extraction helpers for converted documents.

The first implementation focuses on dependency-light extraction:
- Office Open XML containers (.docx, .pptx, .xlsx): extract */media/* files.
- HTML files: copy local <img src="..."> assets next to the batch output.

PDF image extraction is intentionally not implemented here because reliable PDF
asset recovery needs heavier format-specific dependencies. The function returns
an empty list for unsupported formats instead of failing the conversion.
"""

from __future__ import annotations

import html
import re
import os
import shutil
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from .utils import ensure_dir, safe_stem

OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".svg"}


@dataclass(frozen=True)
class AssetRecord:
    """One extracted or copied asset."""

    source: str
    output_path: str
    markdown_path: str
    kind: str = "image"

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-friendly representation."""
        return asdict(self)


def _asset_name(stem: str, index: int, suffix: str) -> str:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return f"{stem}_img_{index:03d}{suffix.lower()}"


def _markdown_relative_path(markdown_path: Path, asset_path: Path) -> str:
    """Return a portable relative path from a Markdown file to an asset."""
    try:
        return Path(os.path.relpath(asset_path, start=markdown_path.parent)).as_posix()
    except ValueError:  # Windows different drives, or other platform edge cases
        return asset_path.as_posix()


def _extract_office_assets(source: Path, markdown_path: Path, assets_dir: Path) -> list[AssetRecord]:
    records: list[AssetRecord] = []
    stem = safe_stem(source)
    try:
        with zipfile.ZipFile(source) as archive:
            media_names = [
                name
                for name in archive.namelist()
                if "/media/" in name.lower() and Path(name).suffix.lower() in IMAGE_EXTENSIONS
            ]
            for index, name in enumerate(sorted(media_names), start=1):
                suffix = Path(name).suffix or ".bin"
                output = assets_dir / _asset_name(stem, index, suffix)
                ensure_dir(output.parent)
                with archive.open(name) as src, output.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                records.append(
                    AssetRecord(
                        source=name,
                        output_path=str(output),
                        markdown_path=_markdown_relative_path(markdown_path, output),
                    )
                )
    except (zipfile.BadZipFile, OSError):
        return []
    return records


def _local_html_image_paths(source: Path) -> list[str]:
    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    paths: list[str] = []
    pattern = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(text):
        raw_src = html.unescape(match.group(2).strip())
        parsed = urlparse(raw_src)
        if parsed.scheme in {"http", "https", "data"} or parsed.netloc:
            continue
        local = unquote(parsed.path)
        if local:
            paths.append(local)
    return paths


def _copy_html_assets(source: Path, markdown_path: Path, assets_dir: Path) -> list[AssetRecord]:
    records: list[AssetRecord] = []
    stem = safe_stem(source)
    seen: set[Path] = set()
    for raw_index, src in enumerate(_local_html_image_paths(source), start=1):
        candidate = (source.parent / src).resolve(strict=False)
        if candidate in seen or not candidate.exists() or not candidate.is_file():
            continue
        if candidate.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        seen.add(candidate)
        output = assets_dir / _asset_name(stem, len(records) + 1, candidate.suffix)
        ensure_dir(output.parent)
        shutil.copy2(candidate, output)
        records.append(
            AssetRecord(
                source=str(candidate),
                output_path=str(output),
                markdown_path=_markdown_relative_path(markdown_path, output),
            )
        )
    return records


def extract_assets(source_path: str | Path, markdown_path: str | Path, assets_dir: str | Path) -> list[AssetRecord]:
    """Extract supported image assets and return records for Markdown linking.

    Unsupported source types return an empty list. This keeps `--extract-assets`
    safe to enable in large mixed folders.
    """
    source = Path(source_path)
    markdown = Path(markdown_path)
    output_dir = ensure_dir(Path(assets_dir))
    suffix = source.suffix.lower()

    if suffix in OFFICE_EXTENSIONS:
        return _extract_office_assets(source, markdown, output_dir)
    if suffix in {".html", ".htm"}:
        return _copy_html_assets(source, markdown, output_dir)
    return []


def append_asset_links(markdown: str, assets: list[AssetRecord]) -> str:
    """Append an extracted-assets section to Markdown when assets exist."""
    if not assets:
        return markdown

    body = markdown.rstrip()
    lines = ["", "", "## Extracted Assets", ""]
    for index, asset in enumerate(assets, start=1):
        lines.append(f"![Extracted asset {index}]({asset.markdown_path})")
    return body + "\n".join(lines) + "\n"
