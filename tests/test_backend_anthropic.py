import json, os
from unittest.mock import patch
from pdf_translator.core.translator.backends.anthropic_api import AnthropicBackend

def test_available_with_key():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        assert AnthropicBackend().is_available() is True
def test_unavailable():
    with patch.dict(os.environ, {}, clear=True):
        assert AnthropicBackend().is_available() is False
def test_translate():
    b = AnthropicBackend()
    with patch.object(b, "_call_api", return_value=json.dumps([{"index": 0, "text": "안녕"}])):
        assert b.translate(["Hello"], "en", "ko") == ["안녕"]
def test_name():
    assert AnthropicBackend().name == "anthropic-api"
