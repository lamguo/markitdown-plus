from markitdown_plus.cleaner import (
    clean_markdown,
    fix_broken_lines,
    is_page_number,
    normalize_heading_spacing,
    normalize_newlines,
    remove_cid_artifacts,
    remove_excess_blank_lines,
    remove_lonely_page_numbers,
    remove_repeated_short_lines,
)


def test_normalize_newlines_windows_and_old_mac():
    assert normalize_newlines("a\r\nb\rc") == "a\nb\nc"


def test_remove_cid_artifacts():
    assert remove_cid_artifacts("A (cid:123) B (CID: 456)") == "A  B "


def test_is_page_number_various_formats():
    samples = ["1", "Page 12", "page 3 of 10", "- 123 -", "– 45 –", "• 12", "[12]", "(23)", "10 / 20", "iv"]
    assert all(is_page_number(sample) for sample in samples)
    assert not is_page_number("Chapter 1")


def test_remove_lonely_page_numbers_various_formats():
    text = "Title\n[1]\nBody\n10 / 20\niv\nEnd"
    cleaned = remove_lonely_page_numbers(text)
    assert "[1]" not in cleaned
    assert "10 / 20" not in cleaned
    assert "\niv\n" not in cleaned
    assert "Body" in cleaned


def test_remove_repeated_short_lines_adaptive_threshold():
    text = "Header\nContent A\nHeader\nContent B"
    assert "Header" not in remove_repeated_short_lines(text)


def test_normalize_heading_spacing():
    assert normalize_heading_spacing("#Title\n## Subtitle") == "# Title\n## Subtitle"


def test_fix_broken_lines_merges_paragraphs_and_preserves_lists_tables_code():
    text = "This study was conducted by Smith et al.,\nwho found results.\n\n- keep list\n| keep | table |\n```\na\nb\n```"
    cleaned = fix_broken_lines(text)
    assert "Smith et al., who found results." in cleaned
    assert "- keep list" in cleaned
    assert "| keep | table |" in cleaned
    assert "```\na\nb\n```" in cleaned


def test_fix_broken_lines_hyphen_removes_only_final_hyphen():
    assert "international" in fix_broken_lines("inter-\nnational")
    assert "data-drivenmodel" in fix_broken_lines("data-driven-\nmodel")


def test_remove_excess_blank_lines_and_trailing_whitespace():
    cleaned = remove_excess_blank_lines("a   \n\n\n\nb")
    assert cleaned == "a\n\nb"


def test_clean_markdown_removes_common_artifacts():
    dirty = """
Report Header

#Title

1

This is a broken
line in a paragraph.

(cid:123)

Report Header

2

Report Header
"""
    cleaned = clean_markdown(dirty)

    assert "(cid:" not in cleaned
    assert "# Title" in cleaned
    assert "\n1\n" not in cleaned
    assert "\n2\n" not in cleaned
    assert "This is a broken line in a paragraph." in cleaned
    assert "Report Header" not in cleaned


def test_normalize_newlines_handles_all_common_newlines():
    from markitdown_plus.cleaner import normalize_newlines

    assert normalize_newlines("a\r\nb\rc\n") == "a\nb\nc\n"
