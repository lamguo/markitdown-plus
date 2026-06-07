"""RAG-ready Markdown chunking utilities."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from .utils import safe_stem, short_hash

TOKEN_RATIOS: dict[str, float] = {
    "gpt4": 0.75,
    "gpt-4": 0.75,
    "gpt-4o": 0.75,
    "deepseek": 0.75,
    "claude": 3.5,
    "gemini": 4.0,
}

CHUNK_STRATEGIES = {"heading", "fixed", "semantic-lite"}

ABBREVIATIONS = (
    "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.", "St.",
    "vs.", "e.g.", "i.e.", "etc.", "Fig.", "Eq.", "No.", "Inc.",
    "Ltd.", "Co.", "U.S.", "U.K.", "Ph.D.", "M.D.", "a.m.", "p.m.",
    "Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.", "Sep.",
    "Sept.", "Oct.", "Nov.", "Dec.",
)

SEMANTIC_BREAK_PREFIXES = (
    "summary", "conclusion", "key takeaway", "key takeaways", "next steps",
    "recommendation", "recommendations", "background", "methodology", "results",
)


@dataclass
class Chunk:
    """One RAG-ready text chunk."""

    id: str
    source: str
    index: int
    heading_path: list[str]
    text: str
    token_estimate: int
    strategy: str = "heading"

    def to_json(self) -> str:
        """Serialize to one JSONL row."""
        return json.dumps(asdict(self), ensure_ascii=False)


def estimate_tokens(text: str, model: str = "gpt4", url_penalty: float = 5.0) -> int:
    """Estimate token count for chunk sizing.

    This is intentionally lightweight and dependency-free. It accounts for CJK
    text, English-like words, URLs, and different rough tokenizer families.
    """
    if not text:
        return 0
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    word_count = len(re.findall(r"\b\w+\b", text))
    url_count = len(re.findall(r"https?://\S+", text))
    ratio = TOKEN_RATIOS.get(model.lower(), TOKEN_RATIOS["gpt4"])
    return max(1, int(cjk_chars / 2 + word_count / ratio + url_count * url_penalty))


def _protect_abbreviations(text: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    protected = text
    for index, abbr in enumerate(ABBREVIATIONS):
        token = f"__MDP_ABBR_{index}__"
        protected = protected.replace(abbr, token)
        replacements[token] = abbr
    return protected, replacements


def _restore_abbreviations(text: str, replacements: dict[str, str]) -> str:
    restored = text
    for token, abbr in replacements.items():
        restored = restored.replace(token, abbr)
    return restored


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences with common abbreviation protection."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    protected, replacements = _protect_abbreviations(normalized)
    parts: list[str] = []
    start = 0
    for match in re.finditer(r"[.!?。！？]+(?:[\"'”’」』\)\]\}】]*)", protected):
        end = match.end()
        next_char = protected[end : end + 1]
        should_split = end == len(protected) or next_char.isspace() or protected[match.start()] in "。！？"
        if should_split:
            piece = protected[start:end].strip()
            if piece:
                parts.append(_restore_abbreviations(piece, replacements))
            start = end
            while start < len(protected) and protected[start].isspace():
                start += 1

    tail = protected[start:].strip()
    if tail:
        parts.append(_restore_abbreviations(tail, replacements))
    return parts or [_restore_abbreviations(protected, replacements)]


def _split_paragraphs(text: str) -> list[str]:
    """Split Markdown into paragraphs without breaking fenced code blocks."""
    paragraphs: list[str] = []
    current: list[str] = []
    in_code_block = False

    def flush() -> None:
        nonlocal current
        if current and any(line.strip() for line in current):
            paragraphs.append("\n".join(current).strip())
        current = []

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            current.append(line)
            in_code_block = not in_code_block
            continue
        if not in_code_block and not stripped:
            flush()
            continue
        current.append(line)

    flush()
    return paragraphs


def _split_oversized_sentence(sentence: str, max_tokens: int, model: str) -> list[str]:
    words = re.findall(r"\S+", sentence)
    if len(words) <= 1:
        return [sentence]

    pieces: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and estimate_tokens(candidate, model=model) > max_tokens:
            pieces.append(" ".join(current).strip())
            current = [word]
        else:
            current.append(word)
    if current:
        pieces.append(" ".join(current).strip())
    return pieces


def _split_long_text(text: str, max_tokens: int, model: str = "gpt4") -> list[str]:
    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append("\n\n".join(current).strip())
            current = []

    for paragraph in paragraphs:
        paragraph_tokens = estimate_tokens(paragraph, model=model)
        if paragraph_tokens > max_tokens:
            flush()
            sentences = _split_sentences(paragraph)
            sentence_buffer: list[str] = []
            for sentence in sentences:
                if estimate_tokens(sentence, model=model) > max_tokens:
                    if sentence_buffer:
                        chunks.append(" ".join(sentence_buffer).strip())
                        sentence_buffer = []
                    chunks.extend(_split_oversized_sentence(sentence, max_tokens=max_tokens, model=model))
                    continue

                candidate = " ".join(sentence_buffer + [sentence]).strip()
                if sentence_buffer and estimate_tokens(candidate, model=model) > max_tokens:
                    chunks.append(" ".join(sentence_buffer).strip())
                    sentence_buffer = [sentence]
                else:
                    sentence_buffer.append(sentence)
            if sentence_buffer:
                chunks.append(" ".join(sentence_buffer).strip())
            continue

        candidate = "\n\n".join(current + [paragraph]).strip()
        if current and estimate_tokens(candidate, model=model) > max_tokens:
            flush()
            current.append(paragraph)
        else:
            current.append(paragraph)
    flush()
    return chunks


def _source_hash(source: str) -> str:
    path = Path(source).expanduser()
    try:
        value = str(path.resolve(strict=False))
    except OSError:
        value = source
    return short_hash(value)


def _make_chunk(
    *,
    source: str,
    source_hash: str,
    source_stem: str,
    index: int,
    heading_path: list[str],
    text: str,
    model: str,
    strategy: str,
) -> Chunk:
    return Chunk(
        id=f"{source_stem}-{source_hash}-{index:04d}",
        source=source,
        index=index,
        heading_path=heading_path,
        text=text.strip(),
        token_estimate=estimate_tokens(text, model=model),
        strategy=strategy,
    )


def _apply_overlap(piece: str, previous_tail: str, overlap: int) -> str:
    if overlap and previous_tail:
        return previous_tail + "\n\n" + piece
    return piece


def _tail(piece: str, overlap: int) -> str:
    if not overlap:
        return ""
    words = re.findall(r"\S+", piece)
    return " ".join(words[-overlap:]) if words else ""


def _sections_from_headings(markdown: str) -> list[tuple[list[str], list[str]]]:
    heading_stack: list[tuple[int, str]] = []
    sections: list[tuple[list[str], list[str]]] = []
    current_lines: list[str] = []

    def current_heading_path() -> list[str]:
        return [title for _, title in heading_stack]

    def flush_section() -> None:
        nonlocal current_lines
        text = "\n".join(current_lines).strip()
        if text:
            sections.append((current_heading_path(), current_lines.copy()))
        current_lines = []

    for line in markdown.split("\n"):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            flush_section()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack = [(lvl, txt) for lvl, txt in heading_stack if lvl < level]
            heading_stack.append((level, title))
            current_lines.append(line)
        else:
            current_lines.append(line)
    flush_section()

    if not sections and markdown.strip():
        sections = [([], markdown.split("\n"))]
    return sections


def _chunk_heading(markdown: str, source: str, max_tokens: int, overlap: int, model: str) -> list[Chunk]:
    result: list[Chunk] = []
    source_hash = _source_hash(source)
    source_stem = safe_stem(Path(source))
    previous_tail = ""

    for heading_path, lines in _sections_from_headings(markdown):
        section_text = "\n".join(lines).strip()
        if not section_text:
            continue
        pieces = _split_long_text(section_text, max_tokens=max_tokens, model=model)
        for piece in pieces:
            text = _apply_overlap(piece, previous_tail, overlap)
            result.append(
                _make_chunk(
                    source=source,
                    source_hash=source_hash,
                    source_stem=source_stem,
                    index=len(result) + 1,
                    heading_path=heading_path,
                    text=text,
                    model=model,
                    strategy="heading",
                )
            )
            previous_tail = _tail(piece, overlap)
    return result


def _chunk_fixed(markdown: str, source: str, max_tokens: int, overlap: int, model: str) -> list[Chunk]:
    result: list[Chunk] = []
    source_hash = _source_hash(source)
    source_stem = safe_stem(Path(source))
    previous_tail = ""
    for piece in _split_long_text(markdown.strip(), max_tokens=max_tokens, model=model):
        text = _apply_overlap(piece, previous_tail, overlap)
        result.append(
            _make_chunk(
                source=source,
                source_hash=source_hash,
                source_stem=source_stem,
                index=len(result) + 1,
                heading_path=[],
                text=text,
                model=model,
                strategy="fixed",
            )
        )
        previous_tail = _tail(piece, overlap)
    return result


def _is_semantic_break(paragraph: str) -> bool:
    stripped = paragraph.strip()
    if not stripped:
        return False
    if re.match(r"^#{1,6}\s+", stripped):
        return True
    lower = re.sub(r"[^a-z\s-]", "", stripped.lower()).strip()
    return any(lower.startswith(prefix) for prefix in SEMANTIC_BREAK_PREFIXES)


def _chunk_semantic_lite(markdown: str, source: str, max_tokens: int, overlap: int, model: str) -> list[Chunk]:
    """Rule-based semantic-lite chunking.

    It keeps paragraphs together, starts new chunks at obvious topical cues, and
    falls back to the same long-text splitter for oversized paragraphs.
    """
    source_hash = _source_hash(source)
    source_stem = safe_stem(Path(source))
    pieces: list[str] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            pieces.append("\n\n".join(current).strip())
            current = []

    for paragraph in _split_paragraphs(markdown):
        if estimate_tokens(paragraph, model=model) > max_tokens:
            flush()
            pieces.extend(_split_long_text(paragraph, max_tokens=max_tokens, model=model))
            continue

        candidate = "\n\n".join(current + [paragraph]).strip()
        should_break = bool(current) and (_is_semantic_break(paragraph) or estimate_tokens(candidate, model=model) > max_tokens)
        if should_break:
            flush()
        current.append(paragraph)
    flush()

    result: list[Chunk] = []
    previous_tail = ""
    for piece in pieces:
        text = _apply_overlap(piece, previous_tail, overlap)
        headings = [m.group(2).strip() for m in re.finditer(r"^(#{1,6})\s+(.+?)$", piece, flags=re.MULTILINE)]
        result.append(
            _make_chunk(
                source=source,
                source_hash=source_hash,
                source_stem=source_stem,
                index=len(result) + 1,
                heading_path=headings[-3:],
                text=text,
                model=model,
                strategy="semantic-lite",
            )
        )
        previous_tail = _tail(piece, overlap)
    return result


def chunk_markdown(
    markdown: str,
    source: str = "document.md",
    max_tokens: int = 800,
    overlap: int = 0,
    model: str = "gpt4",
    strategy: str = "heading",
) -> list[Chunk]:
    """Split Markdown into JSONL-friendly chunks.

    Strategies:
    - heading: heading-aware chunks, the default from v0.1.x.
    - fixed: stable size chunks, ignoring heading boundaries.
    - semantic-lite: dependency-free topical boundary hints.
    """
    if max_tokens < 100:
        raise ValueError("max_tokens must be at least 100")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if strategy not in CHUNK_STRATEGIES:
        raise ValueError(f"Unknown chunk strategy: {strategy}. Choose from: {', '.join(sorted(CHUNK_STRATEGIES))}")

    if not markdown.strip():
        return []
    if strategy == "fixed":
        return _chunk_fixed(markdown, source, max_tokens, overlap, model)
    if strategy == "semantic-lite":
        return _chunk_semantic_lite(markdown, source, max_tokens, overlap, model)
    return _chunk_heading(markdown, source, max_tokens, overlap, model)


def write_jsonl(chunks: Iterable[Chunk], output_path: str | Path) -> Path:
    """Write chunks to a JSONL file."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.to_json() + "\n")
    return output
