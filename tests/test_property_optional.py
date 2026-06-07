import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

from markitdown_plus.chunker import Chunk, chunk_markdown
from markitdown_plus.cleaner import clean_markdown


@given(st.text())
def test_clean_markdown_never_raises(text):
    result = clean_markdown(text)
    assert isinstance(result, str)


@given(st.text(min_size=1))
def test_chunk_markdown_never_raises(text):
    chunks = chunk_markdown(text, source="test.md", max_tokens=200)
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
