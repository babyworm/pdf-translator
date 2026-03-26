import json
from unittest.mock import patch, MagicMock
from pdf_translator.extractor import Element
from pdf_translator.translator import (
    build_prompt,
    parse_codex_response,
    translate_batch,
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
