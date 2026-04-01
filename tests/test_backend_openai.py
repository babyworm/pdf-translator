import json, os
from unittest.mock import patch
from pdf_translator.core.translator.backends.openai_api import OpenAIBackend

def test_available_with_key():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        assert OpenAIBackend().is_available() is True
def test_unavailable():
    with patch.dict(os.environ, {}, clear=True):
        assert OpenAIBackend().is_available() is False
def test_translate():
    b = OpenAIBackend()
    with patch.object(b, "_call_api", return_value=json.dumps([{"index": 0, "text": "안녕"}])):
        assert b.translate(["Hello"], "en", "ko") == ["안녕"]
def test_name():
    assert OpenAIBackend().name == "openai-api"
