import json, os
from unittest.mock import patch
from pdf_translator.core.translator.backends.openrouter_api import OpenRouterBackend

def test_available_with_key():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}):
        assert OpenRouterBackend().is_available() is True
def test_unavailable():
    with patch.dict(os.environ, {}, clear=True):
        assert OpenRouterBackend().is_available() is False
def test_translate():
    b = OpenRouterBackend()
    with patch.object(b, "_call_api", return_value=json.dumps([{"index": 0, "text": "안녕"}])):
        assert b.translate(["Hello"], "en", "ko") == ["안녕"]
def test_name():
    assert OpenRouterBackend().name == "openrouter"
