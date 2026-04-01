from __future__ import annotations

import logging
from pdf_translator.core.translator.backends.codex_cli import CodexCLIBackend
from pdf_translator.core.translator.backends.claude_cli import ClaudeCLIBackend
from pdf_translator.core.translator.backends.gemini_cli import GeminiCLIBackend
from pdf_translator.core.translator.backends.google_translate import GoogleTranslateBackend

logger = logging.getLogger(__name__)


class BackendRouter:
    def __init__(self, effort: str = "low"):
        codex = CodexCLIBackend(effort=effort)
        claude = ClaudeCLIBackend()
        gemini = GeminiCLIBackend()
        google = GoogleTranslateBackend()

        self._cli_backends = [codex, claude, gemini]
        self._api_backends = []  # Phase 2 will add API backends
        self._fallback = google
        self._all_backends = {b.name: b for b in self._cli_backends + self._api_backends}
        if self._fallback:
            self._all_backends[self._fallback.name] = self._fallback

    def select(self, backend_name: str = "auto"):
        if backend_name == "auto":
            return self._auto_select()
        backend = self._all_backends.get(backend_name)
        if backend is None:
            available = ", ".join(self._all_backends.keys())
            raise RuntimeError(f"Unknown backend '{backend_name}'. Available: {available}")
        if not backend.is_available():
            raise RuntimeError(f"Backend '{backend_name}' is not available")
        return backend

    def _auto_select(self):
        for b in self._cli_backends:
            if b.is_available():
                logger.info("Auto-selected backend: %s", b.name)
                return b
        for b in self._api_backends:
            if b.is_available():
                logger.info("Auto-selected backend: %s", b.name)
                return b
        if self._fallback and self._fallback.is_available():
            logger.info("Falling back to: %s", self._fallback.name)
            return self._fallback
        raise RuntimeError("No translation backend available")

    def list_available(self) -> list[str]:
        return [b.name for b in self._all_backends.values() if b.is_available()]
