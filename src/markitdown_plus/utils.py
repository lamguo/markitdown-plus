"""Small utility helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

WINDOWS_UNSAFE_CHARS = r'[<>:"/\\|?*\x00-\x1f]+'


def ensure_dir(path: Path) -> Path:
    """Create a directory if it does not already exist and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_stem(path: Path) -> str:
    """Return a filesystem-safe stem while preserving Unicode names.

    Unlike ASCII-only sanitizers, this keeps Chinese, Japanese, Greek, Cyrillic,
    Arabic, and other valid filename characters. It only replaces characters that
    are unsafe on common filesystems, especially Windows.
    """
    stem = path.stem.strip() or "document"
    stem = re.sub(WINDOWS_UNSAFE_CHARS, "-", stem)
    stem = re.sub(r"-+", "-", stem).strip("-._")
    return stem or "document"


def safe_path_part(value: str) -> str:
    """Sanitize one relative path component while preserving Unicode text."""
    cleaned = re.sub(WINDOWS_UNSAFE_CHARS, "-", value.strip())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-._")
    return cleaned or "document"


def short_hash(value: str, length: int = 8) -> str:
    """Return a short stable hash for IDs."""
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:length]


def make_output_path(source: Path, input_root: Path, output_root: Path, suffix: str) -> Path:
    """Build an output path that preserves relative directory structure."""
    try:
        relative = source.relative_to(input_root)
    except ValueError:
        relative = Path(source.name)

    clean_parts = [safe_path_part(part) for part in relative.parts]
    relative_clean = Path(*clean_parts)
    return output_root / relative_clean.with_suffix(suffix)
