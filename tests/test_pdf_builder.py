import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from pdf_translator.core.extractor import Element
from pdf_translator.core.pdf_builder import _builtin_cjk_fontname, build_pdf


def _create_test_pdf(path: str, text: str = "Hello World") -> None:
    c = canvas.Canvas(path)
    c.drawString(72, 700, text)
    c.save()


def test_build_pdf_creates_file():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "input.pdf")
        dst = str(Path(d) / "output.pdf")
        _create_test_pdf(src)

        elements = [
            Element(
                type="paragraph", content="Hello World", page_number=1,
                bbox=[72, 88, 200, 104], font_size=12.0,
            )
        ]
        translations = {0: "안녕 세계"}

        build_pdf(src, dst, elements, translations)
        assert Path(dst).exists()
        assert Path(dst).stat().st_size > 0


def test_build_pdf_contains_translated_text():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "input.pdf")
        dst = str(Path(d) / "output.pdf")
        _create_test_pdf(src)

        elements = [
            Element(
                type="paragraph", content="Hello World", page_number=1,
                bbox=[72, 88, 200, 104], font_size=12.0,
            )
        ]
        translations = {0: "안녕 세계"}
        build_pdf(src, dst, elements, translations)

        reader = PdfReader(dst)
        page_text = reader.pages[0].extract_text() or ""
        assert "안녕" in page_text


def test_builtin_cjk_fontname_korean():
    assert _builtin_cjk_fontname("안녕하세요") == "korea"


def test_builtin_cjk_fontname_japanese():
    assert _builtin_cjk_fontname("こんにちは") == "japan"


def test_builtin_cjk_fontname_chinese():
    assert _builtin_cjk_fontname("你好世界") == "china-ss"


def test_build_pdf_with_is_scanned_flag():
    """Verify build_pdf accepts is_scanned parameter."""
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "input.pdf")
        dst = str(Path(d) / "output.pdf")
        _create_test_pdf(src)

        elements = [
            Element(
                type="paragraph", content="Hello World", page_number=1,
                bbox=[72, 88, 200, 104], font_size=12.0,
            )
        ]
        translations = {0: "안녕 세계"}
        build_pdf(src, dst, elements, translations, is_scanned=True)
        assert Path(dst).exists()
        assert Path(dst).stat().st_size > 0


def test_build_pdf_japanese_text():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "input.pdf")
        dst = str(Path(d) / "output.pdf")
        _create_test_pdf(src)

        elements = [
            Element(
                type="paragraph", content="Hello", page_number=1,
                bbox=[72, 88, 200, 104], font_size=12.0,
            )
        ]
        translations = {0: "こんにちは"}
        build_pdf(src, dst, elements, translations)

        reader = PdfReader(dst)
        page_text = reader.pages[0].extract_text() or ""
        assert "こんにちは" in page_text


# --- Java integration tests ---


def test_java_available_check():
    """_java_available returns bool without crashing."""
    from pdf_translator.core.pdf_builder import _java_available
    result = _java_available()
    assert isinstance(result, bool)


def test_build_translations_json():
    """_build_translations_json produces valid JSON with skip field."""
    from pdf_translator.core.pdf_builder import _build_translations_json

    elements = [
        Element(type="paragraph", content="Hello", page_number=1,
                bbox=[72, 88, 200, 104], font_size=12.0, text_color=[0.0, 0.0, 0.0]),
        Element(type="paragraph", content="∑i=1 xi", page_number=1,
                bbox=[72, 60, 200, 76], font_size=10.0, text_color=[0.5]),
    ]
    translations = {0: "안녕"}  # index 1 is math, not translated

    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        path = f.name

    _build_translations_json(elements, translations, path)

    with open(path) as f:
        data = json.load(f)

    assert len(data) == 2
    # Translated element
    assert data[0]["text"] == "안녕"
    assert data[0]["skip"] is False
    # Math element — skipped
    assert data[1]["skip"] is True
    assert data[1]["text"] == "∑i=1 xi"  # original preserved

    Path(path).unlink()


def test_build_pdf_pdfbox_integration():
    """build_pdf with Java backend produces valid PDF."""
    from pdf_translator.core.pdf_builder import _java_available

    if not _java_available():
        import pytest
        pytest.skip("Java not available")

    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "input.pdf")
        dst = str(Path(d) / "output.pdf")
        _create_test_pdf(src)

        elements = [
            Element(type="heading", content="Title", page_number=1,
                    bbox=[72, 700, 300, 720], font_size=16.0, text_color=[0.0]),
            Element(type="paragraph", content="Body text", page_number=1,
                    bbox=[72, 88, 500, 104], font_size=12.0, text_color=[0.0, 0.0, 0.0]),
        ]
        translations = {0: "제목", 1: "본문 텍스트"}

        build_pdf(src, dst, elements, translations)
        assert Path(dst).exists()
        assert Path(dst).stat().st_size > 0

        reader = PdfReader(dst)
        assert len(reader.pages) >= 1
