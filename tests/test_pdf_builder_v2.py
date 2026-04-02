import tempfile
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from pdf_translator.core.extractor import Element
from pdf_translator.core.pdf_builder import _fit_fontsize, build_pdf


def _create_test_pdf(path: str) -> None:
    c = canvas.Canvas(path)
    c.drawString(72, 700, "Hello World")
    c.drawString(72, 660, "Test paragraph.")
    c.save()


def test_build_pdf_creates_output():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "src.pdf")
        dst = str(Path(d) / "dst.pdf")
        _create_test_pdf(src)
        elements = [
            Element(type="heading", content="Hello World", page_number=1,
                    bbox=[72, 90, 200, 110], font_size=14.0, text_color=[0, 0, 0]),
        ]
        build_pdf(src, dst, elements, {0: "안녕 세계"})
        assert Path(dst).exists()
        reader = PdfReader(dst)
        assert len(reader.pages) >= 1


def test_build_pdf_preserves_pages():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "src.pdf")
        dst = str(Path(d) / "dst.pdf")
        # Create a 2-page PDF with reportlab
        c = canvas.Canvas(src)
        c.drawString(72, 700, "Page 1")
        c.showPage()
        c.drawString(72, 700, "Page 2")
        c.save()
        build_pdf(src, dst, [], {})
        reader = PdfReader(dst)
        assert len(reader.pages) == 2


def test_fit_fontsize_respects_height():
    long_text = "A" * 200
    size = _fit_fontsize(long_text, 100, 20, 14.0)
    assert size <= 14.0
    assert size >= 4.0


def test_build_pdf_scanned_mode():
    """Scanned mode should produce a valid output PDF."""
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "src.pdf")
        dst = str(Path(d) / "dst.pdf")
        _create_test_pdf(src)
        elements = [
            Element(type="paragraph", content="Hello World", page_number=1,
                    bbox=[72, 90, 200, 110], font_size=12.0, text_color=[0, 0, 0]),
        ]
        build_pdf(src, dst, elements, {0: "안녕 세계"}, is_scanned=True)
        assert Path(dst).exists()
