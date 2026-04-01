from unittest.mock import MagicMock, patch

from pdf_translator.core.translator.backends.google_translate import GoogleTranslateBackend


def test_is_available_with_package():
    with patch.dict("sys.modules", {"deep_translator": MagicMock()}):
        assert GoogleTranslateBackend().is_available() is True

def test_translate_success():
    backend = GoogleTranslateBackend()
    mock_translator = MagicMock()
    mock_translator.translate.side_effect = ["안녕", "세계"]
    with patch("deep_translator.GoogleTranslator", return_value=mock_translator):
        result = backend.translate(["Hello", "World"], "en", "ko")
        assert result == ["안녕", "세계"]

def test_translate_partial_failure():
    backend = GoogleTranslateBackend()
    mock_translator = MagicMock()
    mock_translator.translate.side_effect = ["안녕", Exception("rate limit")]
    with patch("deep_translator.GoogleTranslator", return_value=mock_translator):
        result = backend.translate(["Hello", "World"], "en", "ko")
        assert result[0] == "안녕"
        assert result[1] is None

def test_name_and_type():
    b = GoogleTranslateBackend()
    assert b.name == "google-translate"
    assert b.backend_type == "api"

def test_normalize_lang():
    b = GoogleTranslateBackend()
    assert b._normalize_lang("zh-CN") == "zh"
    assert b._normalize_lang("en-US") == "en"
