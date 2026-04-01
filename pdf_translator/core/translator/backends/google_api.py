from __future__ import annotations

import logging
import os

import requests

from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)

class GoogleAPIBackend:
    name = "google-api"
    backend_type = "api"
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
    def is_available(self) -> bool:
        return bool(os.environ.get("GOOGLE_API_KEY"))
    def translate(self, texts, source_lang, target_lang, glossary=None):
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._call_api(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)
    def _call_api(self, prompt: str) -> str:
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1}},
                timeout=120)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.warning("Google API failed: %s", e)
            return ""
