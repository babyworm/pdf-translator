import tempfile
from pathlib import Path

import fitz

from pdf_translator.ocr.base import OCREngine, OCRResult
from pdf_translator.ocr.detector import is_scanned_page, detect_pdf_type


class FakeOCR:
    name = "fake"

    def is_available(self) -> bool:
        return True

    def extract(self, page_image, lang="en"):
        return [OCRResult(text="Hello", bbox=[0, 0, 100, 20], confidence=0.95)]


def test_ocr_result_creation():
    r = OCRResult(text="Hello", bbox=[0, 0, 100, 20], confidence=0.95)
    assert r.text == "Hello"


def test_fake_ocr_satisfies_protocol():
    assert isinstance(FakeOCR(), OCREngine)


def test_is_scanned_page_text():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "This is a text page with enough content to detect.", fontsize=12)
    assert is_scanned_page(page, threshold=10) is False
    doc.close()


def test_is_scanned_page_empty():
    doc = fitz.open()
    page = doc.new_page()
    assert is_scanned_page(page, threshold=10) is True
    doc.close()


def test_detect_pdf_type_text():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "text.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 100), "A " * 50, fontsize=12)
        doc.save(path)
        doc.close()
        assert detect_pdf_type(path) == "text"


def test_detect_pdf_type_scanned():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "scanned.pdf")
        doc = fitz.open()
        doc.new_page()
        doc.save(path)
        doc.close()
        assert detect_pdf_type(path) == "scanned"
