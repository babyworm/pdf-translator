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


def test_apply_markers_keep():
    b = GoogleTranslateBackend()
    text = "The API uses REST endpoints"
    glossary = {"API": "API", "REST": "REST"}
    marked, markers = b._apply_markers(text, glossary)
    assert "XGLOSS" in marked
    assert len(markers) == 2


def test_apply_markers_translate():
    b = GoogleTranslateBackend()
    text = "The transformer model"
    glossary = {"transformer": "트랜스포머"}
    marked, markers = b._apply_markers(text, glossary)
    assert "transformer" not in marked.lower()
    assert len(markers) == 1


def test_restore_markers():
    b = GoogleTranslateBackend()
    text = "The XGLOSS0X model uses XGLOSS1X"
    markers = {"XGLOSS0X": "트랜스포머", "XGLOSS1X": "어텐션"}
    restored = b._restore_markers(text, markers)
    assert "트랜스포머" in restored
    assert "어텐션" in restored
    assert "XGLOSS" not in restored


def test_apply_markers_empty_glossary():
    b = GoogleTranslateBackend()
    text, markers = b._apply_markers("Hello world", None)
    assert text == "Hello world"
    assert markers == {}


def test_apply_markers_case_insensitive():
    b = GoogleTranslateBackend()
    text = "The api and API are the same"
    glossary = {"API": "API"}
    marked, markers = b._apply_markers(text, glossary)
    assert "api" not in marked.lower() or "XGLOSS" in marked
