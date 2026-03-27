import json
from unittest.mock import patch, MagicMock
from pdf_translator.extractor import Element
from pdf_translator.translator import (
    build_prompt,
    parse_codex_response,
    translate_batch,
    detect_language,
    is_codex_available,
)


def _el(content: str) -> Element:
    return Element(
        type="paragraph", content=content, page_number=1,
        bbox=[0, 0, 100, 20],
    )


def test_build_prompt():
    batch = [_el("Hello"), _el("World")]
    prompt = build_prompt(batch, "en", "ko")
    assert "Hello" in prompt
    assert "Korean" in prompt or "ko" in prompt


def test_parse_codex_response_json():
    response = json.dumps([
        {"index": 0, "text": "안녕하세요"},
        {"index": 1, "text": "세계"},
    ])
    results = parse_codex_response(response, count=2)
    assert results == ["안녕하세요", "세계"]


def test_parse_codex_response_json_undersized():
    """Missing items should be None, not empty strings."""
    response = json.dumps([{"index": 0, "text": "안녕하세요"}])
    results = parse_codex_response(response, count=3)
    assert results == ["안녕하세요", None, None]


def test_parse_codex_response_fallback():
    response = "안녕하세요\n세계"
    results = parse_codex_response(response, count=2)
    assert results == ["안녕하세요", "세계"]


def test_translate_batch_calls_codex():
    batch = [_el("Hello")]
    mock_result = json.dumps([{"index": 0, "text": "안녕하세요"}])

    with patch("pdf_translator.translator._run_codex", return_value=mock_result):
        results = translate_batch(batch, "en", "ko", effort="low")
        assert results == ["안녕하세요"]


def test_translate_batch_returns_none_on_total_failure():
    """Both Codex and Google fail → None results."""
    batch = [_el("Hello"), _el("World")]

    with patch("pdf_translator.translator._run_codex", return_value=""), \
         patch("pdf_translator.translator._translate_batch_google", return_value=[None, None]):
        results = translate_batch(batch, "en", "ko", effort="low")
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


def test_is_codex_available_found():
    with patch("pdf_translator.translator.shutil.which", return_value="/usr/bin/codex"):
        import pdf_translator.translator as t
        t._codex_available = None  # reset cache
        assert is_codex_available() is True
        t._codex_available = None  # cleanup


def test_is_codex_available_not_found():
    with patch("pdf_translator.translator.shutil.which", return_value=None):
        import pdf_translator.translator as t
        t._codex_available = None
        assert is_codex_available() is False
        t._codex_available = None


def test_translate_batch_google_fallback():
    """When codex is unavailable, translate_batch should use Google Translate."""
    batch = [_el("Hello")]
    with patch("pdf_translator.translator.is_codex_available", return_value=False), \
         patch("pdf_translator.translator._translate_batch_google", return_value=["안녕"]) as mock_g:
        results = translate_batch(batch, "en", "ko")
        mock_g.assert_called_once()
        assert results == ["안녕"]


def test_translate_batch_codex_failure_falls_back_to_google():
    """When codex is available but fails, translate_batch should fall back to Google."""
    batch = [_el("Hello")]
    with patch("pdf_translator.translator.is_codex_available", return_value=True), \
         patch("pdf_translator.translator._run_codex", return_value=""), \
         patch("pdf_translator.translator._translate_batch_google", return_value=["안녕"]) as mock_g:
        results = translate_batch(batch, "en", "ko")
        mock_g.assert_called_once()
        assert results == ["안녕"]


def test_translate_batch_google_partial_failure():
    """Google Translate returns None for failed items."""
    from pdf_translator.translator import _translate_batch_google
    batch = [_el("Hello"), _el("World")]
    with patch("deep_translator.GoogleTranslator") as MockGT:
        instance = MockGT.return_value
        instance.translate.side_effect = ["안녕", Exception("rate limit")]
        results = _translate_batch_google(batch, "en", "ko")
        assert results[0] == "안녕"
        assert results[1] is None


def test_normalize_lang():
    from pdf_translator.translator import _normalize_lang
    assert _normalize_lang("zh-CN") == "zh"
    assert _normalize_lang("en-US") == "en"
    assert _normalize_lang("ko") == "ko"
    assert _normalize_lang("en_GB") == "en"
