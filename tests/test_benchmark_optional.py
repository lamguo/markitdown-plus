import pytest

pytest.importorskip("pytest_benchmark")

from markitdown_plus.chunker import chunk_markdown
from markitdown_plus.cleaner import clean_markdown


def test_chunk_markdown_large_document_benchmark(benchmark):
    large_md = "# Title\n\n" + "Hello world. " * 10000
    result = benchmark(chunk_markdown, large_md, source="big.md", max_tokens=500)
    assert len(result) > 0


def test_clean_markdown_large_document_benchmark(benchmark):
    text = ("Hello\nworld. " * 500) + ("(cid:123)" * 100)
    result = benchmark(clean_markdown, text)
    assert "(cid:" not in result
