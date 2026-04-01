from __future__ import annotations

import logging
import os

import requests

from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)

class OpenRouterBackend:
    name = "openrouter"
    backend_type = "api"
    def __init__(self, model: str = "anthropic/claude-sonnet-4"):
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
    def is_available(self) -> bool:
        return bool(os.environ.get("OPENROUTER_API_KEY"))
    def translate(self, texts, source_lang, target_lang, glossary=None):
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._call_api(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)
    def _call_api(self, prompt: str) -> str:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        try:
            resp = requests.post(self.api_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                timeout=120)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("OpenRouter API failed: %s", e)
            return ""
