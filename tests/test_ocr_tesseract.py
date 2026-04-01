from unittest.mock import patch

from pdf_translator.ocr.base import OCRResult
from pdf_translator.ocr.tesseract_engine import TesseractOCREngine


def test_is_available_with_binary():
    with patch("shutil.which", return_value="/usr/bin/tesseract"):
        assert TesseractOCREngine().is_available() is True


def test_is_available_without():
    with patch("shutil.which", return_value=None):
        assert TesseractOCREngine().is_available() is False


def test_extract_returns_results():
    engine = TesseractOCREngine()
    mock = [OCRResult(text="Hello", bbox=[10, 20, 200, 40], confidence=0.90)]
    with patch.object(engine, "extract", return_value=mock):
        results = engine.extract(b"fake", lang="en")
        assert len(results) == 1


def test_name():
    assert TesseractOCREngine().name == "tesseract"
