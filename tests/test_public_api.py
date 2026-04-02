"""Tests for the public Python API (pdf_translator.core.translate_pdf)."""
from unittest.mock import patch

from reportlab.pdfgen import canvas


def test_core_imports():
    from pdf_translator.core import translate_pdf
    assert callable(translate_pdf)


def test_translate_pdf_with_mock(tmp_path):
    from pdf_translator.core import translate_pdf

    pdf_path = tmp_path / "test.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(72, 700, "Hello")
    c.save()

    with patch("pdf_translator.core.extract_pdf", return_value=[]):
        result = translate_pdf(str(pdf_path), target_lang="ko", output_dir=str(tmp_path))
        assert "pdf_path" in result
        assert "md_path" in result
        assert result["segments_total"] == 0
        assert result["segments_translated"] == 0
