"""Thin wrapper around Microsoft MarkItDown."""

from __future__ import annotations

import logging
from pathlib import Path

from .errors import ConversionError, DependencyError

logger = logging.getLogger(__name__)


class PlusConverter:
    """Convert files to Markdown with Microsoft MarkItDown.

    The wrapper keeps markitdown-plus code isolated from small upstream API
    changes. It prefers `result.markdown`, then falls back to older aliases.
    """

    def __init__(self, enable_plugins: bool = False) -> None:
        try:
            from markitdown import MarkItDown  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on environment
            raise DependencyError(
                "markitdown package not found. Run: pip install 'markitdown[all]'"
            ) from exc

        try:
            self._markitdown = MarkItDown(enable_plugins=enable_plugins)
        except TypeError:  # pragma: no cover - compatibility fallback
            if enable_plugins:
                logger.warning(
                    "Installed markitdown version does not support enable_plugins. "
                    "Upgrade with: pip install --upgrade markitdown"
                )
            self._markitdown = MarkItDown()

    def convert_file(self, path: str | Path) -> str:
        """Convert one file and return Markdown text."""
        source = Path(path)
        if not source.exists():
            raise ConversionError(f"File does not exist: {source}")
        if not source.is_file():
            raise ConversionError(f"Input is not a file: {source}")
        if source.stat().st_size == 0:
            logger.warning("Empty file: %s", source)

        try:
            result = self._markitdown.convert(str(source))
        except Exception as exc:
            raise ConversionError(f"Failed to convert {source}: {exc}") from exc

        markdown = getattr(result, "markdown", None)
        if markdown is None:
            markdown = getattr(result, "text_content", None)
        if markdown is None:
            markdown = str(result)
        return str(markdown).strip() + "\n"
