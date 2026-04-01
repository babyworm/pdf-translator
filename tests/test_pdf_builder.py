import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from pdf_translator.core.extractor import Element
from pdf_translator.core.pdf_builder import build_pdf, _builtin_cjk_fontname, _cjk_font_kwargs


def _create_test_pdf(path: str, text: str = "Hello World") -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=12)
    doc.save(path)
    doc.close()


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

        doc = fitz.open(dst)
        page_text = doc[0].get_text()
        doc.close()
        assert "안녕" in page_text


def test_builtin_cjk_fontname_korean():
    assert _builtin_cjk_fontname("안녕하세요") == "korea"


def test_builtin_cjk_fontname_japanese():
    assert _builtin_cjk_fontname("こんにちは") == "japan"


def test_builtin_cjk_fontname_chinese():
    assert _builtin_cjk_fontname("你好世界") == "china-ss"


def test_cjk_font_kwargs_with_file():
    result = _cjk_font_kwargs("안녕", "/fake/font.ttf")
    assert result == {"fontfile": "/fake/font.ttf", "fontname": "CJK"}


def test_cjk_font_kwargs_builtin_fallback():
    result = _cjk_font_kwargs("안녕", None)
    assert result == {"fontname": "korea"}


def test_cjk_font_kwargs_latin_text():
    result = _cjk_font_kwargs("Hello World", None)
    assert result == {}


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

        doc = fitz.open(dst)
        page_text = doc[0].get_text()
        doc.close()
        assert "こんにちは" in page_text
