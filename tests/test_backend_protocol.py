# tests/test_backend_protocol.py
from pdf_translator.core.translator.base import (
    TranslationBackend,
    build_prompt,
    parse_response,
)


def test_build_prompt_contains_text():
    texts = ["Hello", "World"]
    prompt = build_prompt(texts, "en", "ko")
    assert "Hello" in prompt
    assert "Korean" in prompt


def test_build_prompt_with_glossary():
    texts = ["The transformer model"]
    glossary = {"transformer": "트랜스포머"}
    prompt = build_prompt(texts, "en", "ko", glossary=glossary)
    assert "transformer" in prompt
    assert "트랜스포머" in prompt


def test_parse_response_json_array():
    import json
    response = json.dumps([{"index": 0, "text": "안녕"}, {"index": 1, "text": "세계"}])
    result = parse_response(response, count=2)
    assert result == ["안녕", "세계"]


def test_parse_response_plain_lines():
    result = parse_response("안녕\n세계", count=2)
    assert result == ["안녕", "세계"]


def test_parse_response_pads_missing():
    import json
    response = json.dumps([{"index": 0, "text": "안녕"}])
    result = parse_response(response, count=3)
    assert result[0] == "안녕"
    assert result[1] is None
    assert result[2] is None


class FakeBackend:
    name = "fake"
    backend_type = "test"

    def is_available(self) -> bool:
        return True

    def translate(self, texts, source_lang, target_lang, glossary=None):
        return [f"[{target_lang}]{t}" for t in texts]


def test_fake_backend_satisfies_protocol():
    backend = FakeBackend()
    assert isinstance(backend, TranslationBackend)
    result = backend.translate(["Hello"], "en", "ko")
    assert result == ["[ko]Hello"]
