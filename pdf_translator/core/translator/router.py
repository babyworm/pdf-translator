from __future__ import annotations
import logging
from typing import Any

from pdf_translator.core.translator.backends.openai_api import OpenAIBackend
from pdf_translator.core.translator.backends.anthropic_api import AnthropicBackend
from pdf_translator.core.translator.backends.google_api import GoogleAPIBackend
from pdf_translator.core.translator.backends.openrouter_api import OpenRouterBackend

logger = logging.getLogger(__name__)


class TranslatorRouter:
    """Routes translation requests to the best available backend."""

    def __init__(self, preferred: str | None = None):
        self._cli_backends: list[Any] = []
        self._api_backends: list[Any] = [
            OpenRouterBackend(),
            OpenAIBackend(),
            AnthropicBackend(),
            GoogleAPIBackend(),
        ]
        self._fallback: Any = None

        self._all_backends: dict[str, Any] = {
            b.name: b for b in self._cli_backends + self._api_backends
        }
        if self._fallback:
            self._all_backends[self._fallback.name] = self._fallback

        self._preferred = preferred

    def get_backend(self, name: str | None = None) -> Any | None:
        """Get a specific backend by name, or the best available one."""
        if name:
            backend = self._all_backends.get(name)
            if backend and backend.is_available():
                return backend
            logger.warning("Requested backend %r not available", name)
            return None

        if self._preferred:
            backend = self._all_backends.get(self._preferred)
            if backend and backend.is_available():
                return backend

        # Try CLI backends first, then API backends
        for backend in self._cli_backends:
            if backend.is_available():
                return backend
        for backend in self._api_backends:
            if backend.is_available():
                return backend
        if self._fallback and self._fallback.is_available():
            return self._fallback

        return None

    def list_available(self) -> list[str]:
        """List names of all available backends."""
        return [
            name for name, b in self._all_backends.items()
            if b.is_available()
        ]

    def list_all(self) -> list[str]:
        """List names of all registered backends."""
        return list(self._all_backends.keys())
