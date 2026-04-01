import tempfile
from pathlib import Path

import fitz

from pdf_translator.core.extractor import Element, _ocr_fallback, _parse_pages
from pdf_translator.ocr.base import OCRResult


class FakeOCREngine:
    name = "fake"

    def is_available(self):
        return True

    def extract(self, page_image, lang="en"):
        return [
            OCRResult(text="OCR detected text", bbox=[10, 20, 200, 40], confidence=0.9),
            OCRResult(text="Another line", bbox=[10, 50, 200, 70], confidence=0.85),
        ]


def _make_empty_pdf(path):
    """PDF with no text (simulates scanned doc)."""
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()


def _make_text_pdf(path):
    """PDF with text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Hello World", fontsize=12)
    page.insert_text((72, 130), "Second line", fontsize=12)
    page.insert_text((72, 160), "Third line here", fontsize=12)
    page.insert_text((72, 190), "Fourth element", fontsize=12)
    doc.save(str(path))
    doc.close()


def test_ocr_fallback_returns_elements():
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "scan.pdf"
        _make_empty_pdf(pdf)
        engine = FakeOCREngine()
        elements = _ocr_fallback(str(pdf), engine)
        assert len(elements) == 2
        assert elements[0].content == "OCR detected text"
        assert elements[0].page_number == 1
        assert isinstance(elements[0], Element)


def test_ocr_fallback_with_pages():
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "scan.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.new_page()
        doc.new_page()
        doc.save(str(pdf))
        doc.close()

        engine = FakeOCREngine()
        elements = _ocr_fallback(str(pdf), engine, pages="1,3")
        # 2 results per page, 2 pages selected
        assert len(elements) == 4
        assert elements[0].page_number == 1
        assert elements[2].page_number == 3


def test_parse_pages_single():
    assert _parse_pages("1", 10) == [0]
    assert _parse_pages("3", 10) == [2]


def test_parse_pages_range():
    assert _parse_pages("1-3", 10) == [0, 1, 2]


def test_parse_pages_mixed():
    assert _parse_pages("1,3,5-7", 10) == [0, 2, 4, 5, 6]


def test_parse_pages_out_of_range():
    assert _parse_pages("99", 5) == []
