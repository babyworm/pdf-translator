from unittest.mock import MagicMock, patch

from pdf_translator.ocr.base import OCRResult
from pdf_translator.ocr.surya_engine import SuryaOCREngine


def test_is_available_with_package():
    with patch.dict("sys.modules", {"surya": MagicMock()}):
        assert SuryaOCREngine().is_available() is True


def test_extract_returns_results():
    engine = SuryaOCREngine()
    mock_results = [OCRResult(text="Hello", bbox=[10, 20, 200, 40], confidence=0.92)]
    with patch.object(engine, "extract", return_value=mock_results):
        results = engine.extract(b"fake", lang="en")
        assert len(results) == 1
        assert results[0].text == "Hello"


def test_name():
    assert SuryaOCREngine().name == "surya"
