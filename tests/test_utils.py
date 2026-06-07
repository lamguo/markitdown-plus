from pathlib import Path

from markitdown_plus.utils import make_output_path, safe_stem, short_hash


def test_safe_stem_preserves_unicode():
    assert safe_stem(Path("报告.pdf")) == "报告"
    assert safe_stem(Path("研究数据_2024.xlsx")) == "研究数据_2024"
    assert safe_stem(Path("απόδοση.docx")) == "απόδοση"


def test_safe_stem_replaces_unsafe_chars():
    assert safe_stem(Path('bad:name?.pdf')) == "bad-name"


def test_short_hash_stability():
    assert short_hash("hello") == short_hash("hello")
    assert short_hash("hello") != short_hash("world")


def test_make_output_path_preserves_subdirs_and_unicode(tmp_path: Path):
    root = tmp_path / "docs"
    source = root / "子目录" / "报告.pdf"
    output = tmp_path / "out"
    result = make_output_path(source, root, output, ".md")
    assert result == output / "子目录" / "报告.md"
