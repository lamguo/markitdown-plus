from pathlib import Path

import pytest

from markitdown_plus.converter import PlusConverter
from markitdown_plus.errors import ConversionError, DependencyError


def test_converter_missing_file_raises_conversion_error(monkeypatch: pytest.MonkeyPatch):
    class FakeMarkItDown:
        def __init__(self, enable_plugins: bool = False) -> None:
            pass

    import sys
    import types

    fake_module = types.SimpleNamespace(MarkItDown=FakeMarkItDown)
    monkeypatch.setitem(sys.modules, "markitdown", fake_module)

    converter = PlusConverter()
    with pytest.raises(ConversionError):
        converter.convert_file("missing.pdf")


def test_converter_dependency_error_message(monkeypatch: pytest.MonkeyPatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "markitdown":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(DependencyError) as exc_info:
        PlusConverter()
    assert "markitdown[all]" in str(exc_info.value)


def test_converter_returns_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    class Result:
        markdown = "# Hello"

    class FakeMarkItDown:
        def __init__(self, enable_plugins: bool = False) -> None:
            self.enable_plugins = enable_plugins

        def convert(self, path: str) -> Result:
            return Result()

    import sys
    import types

    fake_module = types.SimpleNamespace(MarkItDown=FakeMarkItDown)
    monkeypatch.setitem(sys.modules, "markitdown", fake_module)
    source = tmp_path / "a.txt"
    source.write_text("hello", encoding="utf-8")

    converter = PlusConverter(enable_plugins=True)
    assert converter.convert_file(source) == "# Hello\n"
