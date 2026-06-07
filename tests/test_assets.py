import zipfile
from pathlib import Path

from markitdown_plus.assets import AssetRecord, append_asset_links, extract_assets


def test_asset_record_to_dict():
    record = AssetRecord(source="a", output_path="b", markdown_path="c")
    assert record.to_dict()["kind"] == "image"


def test_extract_office_assets_from_docx_zip(tmp_path: Path):
    source = tmp_path / "报告.docx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("word/media/image1.PNG", b"image-data")
        archive.writestr("word/document.xml", "<xml />")
    markdown_path = tmp_path / "out" / "markdown" / "报告.md"
    assets_dir = tmp_path / "out" / "assets"

    assets = extract_assets(source, markdown_path, assets_dir)

    assert len(assets) == 1
    assert Path(assets[0].output_path).exists()
    assert assets[0].markdown_path == "../assets/报告_img_001.png"


def test_extract_office_assets_bad_zip_returns_empty(tmp_path: Path):
    source = tmp_path / "bad.docx"
    source.write_text("not a zip", encoding="utf-8")
    assert extract_assets(source, tmp_path / "out.md", tmp_path / "assets") == []


def test_extract_html_local_image_assets(tmp_path: Path):
    image = tmp_path / "pic.jpg"
    image.write_bytes(b"jpg")
    html = tmp_path / "page.html"
    html.write_text('<img src="pic.jpg"><img src="https://example.com/remote.jpg">', encoding="utf-8")
    markdown_path = tmp_path / "out" / "markdown" / "page.md"
    assets_dir = tmp_path / "out" / "assets"

    assets = extract_assets(html, markdown_path, assets_dir)

    assert len(assets) == 1
    assert Path(assets[0].output_path).read_bytes() == b"jpg"
    assert assets[0].markdown_path == "../assets/page_img_001.jpg"


def test_extract_assets_unsupported_type_returns_empty(tmp_path: Path):
    source = tmp_path / "a.txt"
    source.write_text("hello", encoding="utf-8")
    assert extract_assets(source, tmp_path / "a.md", tmp_path / "assets") == []


def test_append_asset_links():
    markdown = "# Title\n"
    linked = append_asset_links(markdown, [AssetRecord("a", "b", "../assets/a.png")])
    assert "## Extracted Assets" in linked
    assert "![Extracted asset 1](../assets/a.png)" in linked
    assert append_asset_links(markdown, []) == markdown
