import json
from unittest.mock import patch
from pdf_translator.core.translator.backends.gemini_cli import GeminiCLIBackend

def test_is_available_true():
    with patch("shutil.which", return_value="/usr/bin/gemini"):
        assert GeminiCLIBackend().is_available() is True

def test_is_available_false():
    with patch("shutil.which", return_value=None):
        assert GeminiCLIBackend().is_available() is False

def test_translate_success():
    backend = GeminiCLIBackend()
    with patch.object(backend, "_run_cli", return_value=json.dumps([{"index": 0, "text": "안녕"}])):
        assert backend.translate(["Hello"], "en", "ko") == ["안녕"]

def test_name_and_type():
    b = GeminiCLIBackend()
    assert b.name == "gemini-cli"
    assert b.backend_type == "cli"
