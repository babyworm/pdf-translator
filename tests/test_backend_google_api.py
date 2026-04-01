import json, os
from unittest.mock import patch
from pdf_translator.core.translator.backends.google_api import GoogleAPIBackend

def test_available_with_key():
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test"}):
        assert GoogleAPIBackend().is_available() is True
def test_unavailable():
    with patch.dict(os.environ, {}, clear=True):
        assert GoogleAPIBackend().is_available() is False
def test_translate():
    b = GoogleAPIBackend()
    with patch.object(b, "_call_api", return_value=json.dumps([{"index": 0, "text": "안녕"}])):
        assert b.translate(["Hello"], "en", "ko") == ["안녕"]
def test_name():
    assert GoogleAPIBackend().name == "google-api"
