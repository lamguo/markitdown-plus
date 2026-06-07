"""Markdown cleanup utilities."""

from __future__ import annotations

import re
from collections import Counter

PAGE_NUM_PATTERNS = [
    re.compile(r"^\d{1,5}$"),
    re.compile(r"^page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^[•∙\-–—\[\]\(\)]?\s*\d{1,5}\s*[•∙\-–—\[\]\(\)]?$"),
    re.compile(r"^\d{1,5}\s*/\s*\d{1,5}$"),
    re.compile(r"^[•∙\-–—]?\s*[ivxlcdm]{1,12}\s*[•∙\-–—]?$", re.IGNORECASE),
]

SENTENCE_END = (".", "!", "?", "。", "！", "？")
STRUCTURAL_PREFIXES = ("#", "- ", "* ", "> ", "|")


def normalize_newlines(text: str) -> str:
    """Normalize Windows, Unix, and old Mac newlines with a single regex pass."""
    return re.sub(r"\r\n?|\n", "\n", text)


def remove_cid_artifacts(text: str) -> str:
    """Remove common PDF extraction artifacts such as `(cid:123)`."""
    return re.sub(r"\(cid:\s*\d+\)", "", text, flags=re.IGNORECASE)


def is_page_number(line: str) -> bool:
    """Return True when a line looks like a standalone page marker."""
    stripped = line.strip()
    if not stripped:
        return False
    return any(pattern.fullmatch(stripped) for pattern in PAGE_NUM_PATTERNS)


def remove_lonely_page_numbers(text: str) -> str:
    """Remove lines that are only page numbers or simple page markers."""
    return "\n".join(line for line in text.split("\n") if not is_page_number(line))


def remove_repeated_short_lines(text: str, min_repeats: int | None = None) -> str:
    """Remove repeated short non-heading lines that often come from headers/footers.

    The threshold adapts to the document length. Short documents can have a
    repeated header/footer only twice; long documents need stronger evidence so
    legitimate repeated table rows are less likely to be removed.
    """
    raw_lines = text.split("\n")
    line_count = len(raw_lines)
    if min_repeats is None:
        min_repeats = 2 if line_count < 80 else max(3, line_count // 25)

    normalized = [re.sub(r"\s+", " ", line.strip()) for line in raw_lines]

    def is_candidate(line: str) -> bool:
        if not (2 <= len(line) <= 90):
            return False
        if line.startswith(STRUCTURAL_PREFIXES):
            return False
        if re.match(r"^\d+[.)]\s+", line):
            return False
        return True

    counts = Counter(line for line in normalized if is_candidate(line))

    cleaned: list[str] = []
    for original, key in zip(raw_lines, normalized, strict=True):
        if key and is_candidate(key) and counts[key] >= min_repeats:
            continue
        cleaned.append(original)
    return "\n".join(cleaned)


def normalize_heading_spacing(text: str) -> str:
    """Ensure Markdown headings have one space after # markers."""
    return re.sub(r"^(#{1,6})([^#\s].*)$", r"\1 \2", text, flags=re.MULTILINE)


def fix_broken_lines(text: str) -> str:
    """Repair simple PDF line breaks inside paragraphs.

    This intentionally stays conservative so tables, lists, blockquotes, and code
    blocks are not destroyed.
    """
    lines = text.split("\n")
    output: list[str] = []
    buffer = ""
    in_code_block = False

    def flush() -> None:
        nonlocal buffer
        if buffer:
            output.append(buffer.strip())
            buffer = ""

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush()
            output.append(line.rstrip())
            in_code_block = not in_code_block
            continue

        if in_code_block:
            output.append(line.rstrip())
            continue

        if not stripped:
            flush()
            output.append("")
            continue

        if stripped.startswith(STRUCTURAL_PREFIXES) or re.match(r"^\d+[.)]\s+", stripped):
            flush()
            output.append(line.rstrip())
            continue

        if buffer:
            if buffer.endswith("-"):
                buffer = buffer[:-1] + stripped
            elif buffer.endswith("/"):
                buffer = buffer[:-1] + stripped
            elif not buffer.endswith(SENTENCE_END):
                buffer += " " + stripped
            else:
                flush()
                buffer = stripped
        else:
            buffer = stripped

    flush()
    return "\n".join(output)


def remove_excess_blank_lines(text: str, trim_trailing_whitespace: bool = True) -> str:
    """Collapse 3+ blank lines to two blank lines.

    Trailing whitespace trimming stays enabled by default because converted PDF
    text often contains stray spaces that harm Markdown diffs.
    """
    if trim_trailing_whitespace:
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", text)


def clean_markdown(text: str) -> str:
    """Run the default Markdown cleanup pipeline."""
    text = normalize_newlines(text)
    text = remove_cid_artifacts(text)
    text = remove_lonely_page_numbers(text)
    text = remove_repeated_short_lines(text)
    text = normalize_heading_spacing(text)
    text = fix_broken_lines(text)
    text = remove_excess_blank_lines(text)
    return text.strip() + "\n" if text.strip() else ""
