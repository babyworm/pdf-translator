# tests/test_translator.py
import json
from unittest.mock import MagicMock, patch

from pdf_translator.core.extractor import Element
from pdf_translator.core.translator import detect_language
from pdf_translator.core.translator.backends.codex_cli import CodexCLIBackend
from pdf_translator.core.translator.backends.google_translate import GoogleTranslateBackend
from pdf_translator.core.translator.base import build_prompt, parse_response


def _el(content: str) -> Element:
    return Element(type="paragraph", content=content, page_number=1, bbox=[0, 0, 100, 20])


def test_build_prompt():
    prompt = build_prompt(["Hello", "World"], "en", "ko")
    assert "Hello" in prompt
    assert "Korean" in prompt or "ko" in prompt


def test_parse_response_json():
    response = json.dumps([{"index": 0, "text": "안녕하세요"}, {"index": 1, "text": "세계"}])
    results = parse_response(response, count=2)
    assert results == ["안녕하세요", "세계"]


def test_parse_response_json_undersized():
    response = json.dumps([{"index": 0, "text": "안녕하세요"}])
    results = parse_response(response, count=3)
    assert results == ["안녕하세요", None, None]


def test_parse_response_fallback():
    results = parse_response("안녕하세요\n세계", count=2)
    assert results == ["안녕하세요", "세계"]


def test_codex_backend_translate():
    backend = CodexCLIBackend()
    mock_result = json.dumps([{"index": 0, "text": "안녕하세요"}])
    with patch.object(backend, "_run_cli", return_value=mock_result):
        results = backend.translate(["Hello"], "en", "ko")
        assert results == ["안녕하세요"]


def test_codex_backend_failure():
    backend = CodexCLIBackend()
    with patch.object(backend, "_run_cli", return_value=""):
        results = backend.translate(["Hello", "World"], "en", "ko")
        assert results == [None, None]


def test_detect_language_english():
    elements = [_el("This is a sample English paragraph for detection.")]
    assert detect_language(elements) == "en"


def test_detect_language_korean():
    elements = [_el("이것은 한국어 텍스트 샘플입니다. 언어 감지를 테스트합니다.")]
    assert detect_language(elements) == "ko"


def test_detect_language_empty_fallback():
    elements = [_el(""), _el("   ")]
    assert detect_language(elements) == "en"


def test_codex_available():
    with patch("shutil.which", return_value="/usr/bin/codex"):
        assert CodexCLIBackend().is_available() is True


def test_codex_not_available():
    with patch("shutil.which", return_value=None):
        assert CodexCLIBackend().is_available() is False


def test_google_translate_fallback():
    backend = GoogleTranslateBackend()
    mock_translator = MagicMock()
    mock_translator.translate.return_value = "안녕"
    with patch("deep_translator.GoogleTranslator", return_value=mock_translator):
        results = backend.translate(["Hello"], "en", "ko")
        assert results == ["안녕"]


def test_google_translate_partial_failure():
    backend = GoogleTranslateBackend()
    mock_translator = MagicMock()
    mock_translator.translate.side_effect = ["안녕", Exception("rate limit")]
    with patch("deep_translator.GoogleTranslator", return_value=mock_translator):
        results = backend.translate(["Hello", "World"], "en", "ko")
        assert results[0] == "안녕"
        assert results[1] is None


def test_normalize_lang():
    assert GoogleTranslateBackend._normalize_lang("zh-CN") == "zh"
    assert GoogleTranslateBackend._normalize_lang("en-US") == "en"
    assert GoogleTranslateBackend._normalize_lang("ko") == "ko"
    assert GoogleTranslateBackend._normalize_lang("en_GB") == "en"
    assert GoogleTranslateBackend._normalize_lang(" en-US ") == "en"
