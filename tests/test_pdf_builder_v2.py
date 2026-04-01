import tempfile
from pathlib import Path
import fitz
from pdf_translator.core.extractor import Element
from pdf_translator.core.pdf_builder import build_pdf, _sample_background_color, _fit_fontsize_v2


def _create_test_pdf(path: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Hello World", fontsize=14, color=(0, 0, 0))
    page.insert_text((72, 140), "Test paragraph.", fontsize=12, color=(0.2, 0.2, 0.8))
    doc.save(path)
    doc.close()


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
        doc = fitz.open(dst)
        assert len(doc) >= 1
        doc.close()


def test_build_pdf_preserves_pages():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "src.pdf")
        dst = str(Path(d) / "dst.pdf")
        doc = fitz.open()
        doc.new_page()
        doc.new_page()
        doc.save(src)
        doc.close()
        build_pdf(src, dst, [], {})
        out = fitz.open(dst)
        assert len(out) == 2
        out.close()


def test_fit_fontsize_v2_respects_height():
    rect = fitz.Rect(0, 0, 100, 20)
    long_text = "A" * 200
    size = _fit_fontsize_v2(long_text, rect, 14.0)
    assert size <= 14.0
    assert size >= 4.0


def test_sample_background_color_white():
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(10, 10, 50, 50)
    pixmap = page.get_pixmap(clip=rect)
    color = _sample_background_color(pixmap)
    assert all(c > 0.95 for c in color)
    doc.close()


def test_build_pdf_scanned_mode():
    """Scanned mode should use background color fill instead of redaction."""
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
