from unittest.mock import MagicMock
from pdf_translator.core.translator.router import BackendRouter


def test_auto_select_first_available_cli():
    router = BackendRouter()
    mock = MagicMock()
    mock.is_available.return_value = True
    mock.name = "claude-cli"
    mock.backend_type = "cli"
    router._cli_backends = [mock]
    router._api_backends = []
    assert router.select("auto") is mock


def test_auto_select_falls_to_api():
    router = BackendRouter()
    cli = MagicMock(); cli.is_available.return_value = False
    api = MagicMock(); api.is_available.return_value = True; api.name = "openai"
    router._cli_backends = [cli]
    router._api_backends = [api]
    router._fallback = None
    assert router.select("auto") is api


def test_explicit_select():
    router = BackendRouter()
    mock = MagicMock(); mock.name = "claude-cli"; mock.is_available.return_value = True
    router._all_backends = {"claude-cli": mock}
    assert router.select("claude-cli") is mock


def test_explicit_unavailable_raises():
    router = BackendRouter()
    mock = MagicMock(); mock.name = "claude-cli"; mock.is_available.return_value = False
    router._all_backends = {"claude-cli": mock}
    try:
        router.select("claude-cli")
        assert False, "Should raise"
    except RuntimeError as e:
        assert "claude-cli" in str(e)


def test_auto_fallback_google():
    router = BackendRouter()
    cli = MagicMock(); cli.is_available.return_value = False
    fb = MagicMock(); fb.is_available.return_value = True; fb.name = "google-translate"
    router._cli_backends = [cli]
    router._api_backends = []
    router._fallback = fb
    assert router.select("auto") is fb
