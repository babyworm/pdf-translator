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


# --- Layout-aware prompt tests ---

def test_build_prompt_with_layout_includes_bbox():
    from pdf_translator.core.translator.base import build_prompt_with_layout
    items = [
        {"index": 0, "text": "Abstract", "type": "heading", "bbox_w": 44, "bbox_h": 16},
        {"index": 1, "text": "We propose a model.", "type": "paragraph", "bbox_w": 396, "bbox_h": 55},
    ]
    prompt = build_prompt_with_layout(items, "en", "ko")
    assert "bbox" in prompt or "area" in prompt.lower()
    assert "Abstract" in prompt
    assert "action" in prompt.lower()


def test_build_prompt_with_layout_formula():
    from pdf_translator.core.translator.base import build_prompt_with_layout
    items = [
        {"index": 0, "text": "FFN(x) = max(0,xW1 + b1)W2 + b2", "type": "paragraph", "bbox_w": 200, "bbox_h": 12},
    ]
    prompt = build_prompt_with_layout(items, "en", "ko")
    assert "skip" in prompt.lower()  # should instruct about skip action


def test_parse_response_with_action():
    import json
    from pdf_translator.core.translator.base import parse_response_with_action
    response = json.dumps([
        {"index": 0, "action": "translate", "text": "초록"},
        {"index": 1, "action": "translate", "text": "우리는 모델을 제안한다."},
        {"index": 2, "action": "skip"},
    ])
    result = parse_response_with_action(response, count=3)
    assert result[0] == {"action": "translate", "text": "초록"}
    assert result[1] == {"action": "translate", "text": "우리는 모델을 제안한다."}
    assert result[2] == {"action": "skip", "text": None}


def test_parse_response_with_action_fallback():
    """If LLM returns old format (no action), treat all as translate."""
    import json
    from pdf_translator.core.translator.base import parse_response_with_action
    response = json.dumps([
        {"index": 0, "text": "초록"},
        {"index": 1, "text": "본문"},
    ])
    result = parse_response_with_action(response, count=2)
    assert result[0]["action"] == "translate"
    assert result[0]["text"] == "초록"


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
