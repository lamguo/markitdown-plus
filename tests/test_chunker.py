import json
from pathlib import Path

from markitdown_plus.chunker import (
    _split_long_text,
    _split_sentences,
    chunk_markdown,
    estimate_tokens,
    write_jsonl,
)


def test_estimate_tokens_returns_positive_number():
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("中文测试") > 0


def test_estimate_tokens_counts_urls_with_penalty():
    plain = estimate_tokens("visit example")
    with_url = estimate_tokens("visit https://example.com/a/very/long/path")
    assert with_url > plain


def test_chunk_markdown_keeps_heading_path():
    markdown = """# Title

Intro paragraph.

## Details

This is a detailed paragraph about the document.
"""
    chunks = chunk_markdown(markdown, source="report.md", max_tokens=200)

    assert chunks
    assert chunks[0].source == "report.md"
    assert chunks[0].heading_path == ["Title"]
    assert any(chunk.heading_path == ["Title", "Details"] for chunk in chunks)


def test_chunk_markdown_overlap_across_sections():
    first = "one two three four five"
    markdown = f"# A\n\n{first}\n\n# B\n\nsecond section"
    chunks = chunk_markdown(markdown, source="report.md", max_tokens=200, overlap=3)
    assert len(chunks) == 2
    assert chunks[1].text.startswith("three four five")


def test_chunk_ids_are_unique_for_same_stem_different_paths(tmp_path: Path):
    a = tmp_path / "docs" / "report.pdf"
    b = tmp_path / "backup" / "report.pdf"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_text("a", encoding="utf-8")
    b.write_text("b", encoding="utf-8")

    chunk_a = chunk_markdown("# A\n\nHello", source=str(a), max_tokens=200)[0]
    chunk_b = chunk_markdown("# A\n\nHello", source=str(b), max_tokens=200)[0]

    assert chunk_a.id != chunk_b.id


def test_chunk_to_json_is_valid_json():
    chunks = chunk_markdown("# Title\n\nHello world.", source="a.md", max_tokens=200)
    payload = json.loads(chunks[0].to_json())
    assert payload["source"] == "a.md"
    assert "text" in payload


def test_chunk_validation_errors():
    try:
        chunk_markdown("hello", max_tokens=50)
    except ValueError as exc:
        assert "max_tokens" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

    try:
        chunk_markdown("hello", overlap=-1)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_write_jsonl(tmp_path: Path):
    output = tmp_path / "chunks.jsonl"
    chunks = chunk_markdown("# Title\n\nHello world.", source="a.md", max_tokens=200)
    write_jsonl(chunks, output)
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8").splitlines()[0])["text"]


def test_split_sentences_handles_abbreviations_and_line_breaks():
    text = "Dr. Smith reviewed Fig. 1.\nThe U.S. team agreed. Next step followed."
    sentences = _split_sentences(text)
    assert "Dr. Smith reviewed Fig. 1." in sentences[0]
    assert any(sentence.startswith("The U.S. team") for sentence in sentences)
    assert sentences[-1] == "Next step followed."


def test_split_long_text_keeps_fenced_code_block_together():
    markdown = """```python
print('first')

print('second')
```

Outside paragraph."""
    pieces = _split_long_text(markdown, max_tokens=200)
    assert pieces[0].startswith("```python")
    assert "print('second')" in pieces[0]
    assert "Outside paragraph." in pieces[-1]


def test_chunk_fixed_strategy_has_no_heading_path():
    markdown = "# Title\n\n" + "hello world. " * 300
    chunks = chunk_markdown(markdown, source="fixed.md", max_tokens=200, strategy="fixed")
    assert chunks
    assert all(chunk.strategy == "fixed" for chunk in chunks)
    assert all(chunk.heading_path == [] for chunk in chunks)


def test_chunk_semantic_lite_splits_on_conclusion():
    markdown = "Intro paragraph. " * 80 + "\n\nConclusion\n\nFinal paragraph. " * 20
    chunks = chunk_markdown(markdown, source="semantic.md", max_tokens=200, strategy="semantic-lite")
    assert chunks
    assert all(chunk.strategy == "semantic-lite" for chunk in chunks)
    assert any("Conclusion" in chunk.text for chunk in chunks)


def test_chunk_empty_markdown_returns_empty():
    assert chunk_markdown("   ", strategy="fixed") == []


def test_chunk_unknown_strategy_raises():
    try:
        chunk_markdown("hello", max_tokens=200, strategy="unknown")
    except ValueError as exc:
        assert "Unknown chunk strategy" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_estimate_tokens_model_profiles():
    text = "hello world " * 10
    assert estimate_tokens(text, model="gpt4") >= estimate_tokens(text, model="claude")
    assert estimate_tokens(text, model="missing-profile") == estimate_tokens(text, model="gpt4")


def test_write_jsonl_empty_list(tmp_path: Path):
    output = tmp_path / "empty.jsonl"
    write_jsonl([], output)
    assert output.exists()
    assert output.read_text(encoding="utf-8") == ""
