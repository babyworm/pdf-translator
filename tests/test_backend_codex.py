import json
from unittest.mock import patch

from pdf_translator.core.translator.backends.codex_cli import CodexCLIBackend


def test_is_available_true():
    with patch("shutil.which", return_value="/usr/bin/codex"):
        assert CodexCLIBackend().is_available() is True

def test_is_available_false():
    with patch("shutil.which", return_value=None):
        assert CodexCLIBackend().is_available() is False

def test_translate_success():
    backend = CodexCLIBackend()
    with patch.object(backend, "_run_cli", return_value=json.dumps([{"index": 0, "text": "안녕"}])):
        assert backend.translate(["Hello"], "en", "ko") == ["안녕"]

def test_translate_failure():
    backend = CodexCLIBackend()
    with patch.object(backend, "_run_cli", return_value=""):
        assert backend.translate(["Hello"], "en", "ko") == [None]

def test_name_and_type():
    b = CodexCLIBackend()
    assert b.name == "codex"
    assert b.backend_type == "cli"
