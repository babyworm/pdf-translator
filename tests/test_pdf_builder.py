import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from pdf_translator.core.extractor import Element
from pdf_translator.core.pdf_builder import _builtin_cjk_fontname, build_pdf


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

        doc = fitz.open(dst)
        page_text = doc[0].get_text()
        doc.close()
        assert "こんにちは" in page_text
