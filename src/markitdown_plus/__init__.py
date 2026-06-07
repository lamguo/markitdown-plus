"""MarkItDown Plus.

Batch conversion, Markdown cleanup, JSONL chunks, and manifest output for
Microsoft MarkItDown powered document pipelines.
"""

from .__about__ import __version__
from .cleaner import clean_markdown
from .chunker import chunk_markdown
from .converter import PlusConverter

__all__ = ["PlusConverter", "clean_markdown", "chunk_markdown", "__version__"]
