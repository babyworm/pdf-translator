import tempfile
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from pdf_translator.ocr.base import OCREngine, OCRResult
from pdf_translator.ocr.detector import detect_pdf_type, is_scanned_page


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
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "text.pdf")
        c = canvas.Canvas(path)
        c.drawString(72, 700, "This is a text page with enough content to detect.")
        c.save()
        reader = PdfReader(path)
        assert is_scanned_page(reader.pages[0], threshold=10) is False


def test_is_scanned_page_empty():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "empty.pdf")
        c = canvas.Canvas(path)
        c.showPage()  # create a blank page with no text
        c.save()
        reader = PdfReader(path)
        assert is_scanned_page(reader.pages[0], threshold=10) is True


def test_detect_pdf_type_text():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "text.pdf")
        c = canvas.Canvas(path)
        c.drawString(72, 700, "A " * 50)
        c.save()
        assert detect_pdf_type(path) == "text"


def test_detect_pdf_type_scanned():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "scanned.pdf")
        c = canvas.Canvas(path)
        c.showPage()  # create a blank page with no text
        c.save()
        assert detect_pdf_type(path) == "scanned"
