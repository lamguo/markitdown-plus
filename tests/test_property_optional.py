
from markitdown_plus.chunker import chunk_markdown
from markitdown_plus.cleaner import clean_markdown

try:
    from hypothesis import given
    from hypothesis import strategies as st
except ImportError:
    given = st = None

if given and st:

    @given(st.text())
    def test_clean_markdown_never_raises(text):
        result = clean_markdown(text)
        assert isinstance(result, str)

    @given(st.text())
    def test_chunk_markdown_never_raises(text):
        chunk_markdown(text)
