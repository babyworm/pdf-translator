from __future__ import annotations

import logging
import os

import requests

from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)

class AnthropicBackend:
    name = "anthropic-api"
    backend_type = "api"
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self.api_url = "https://api.anthropic.com/v1/messages"
    def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    def translate(self, texts, source_lang, target_lang, glossary=None):
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._call_api(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)
    def _call_api(self, prompt: str) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        try:
            resp = requests.post(self.api_url,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": self.model, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]},
                timeout=120)
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        except Exception as e:
            logger.warning("Anthropic API failed: %s", e)
            return ""
