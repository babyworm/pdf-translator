from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_GOOGLE_LANG_MAP = {"zh": "zh-CN"}


class GoogleTranslateBackend:
    name = "google-translate"
    backend_type = "api"

    def is_available(self) -> bool:
        try:
            import deep_translator  # noqa: F401
            return True
        except ImportError:
            return False

    def translate(self, texts, source_lang, target_lang, glossary=None):
        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            return [None] * len(texts)

        src = self._normalize_lang(source_lang)
        tgt = self._normalize_lang(target_lang)
        src = _GOOGLE_LANG_MAP.get(src, src)
        tgt = _GOOGLE_LANG_MAP.get(tgt, tgt)
        translator = GoogleTranslator(source=src, target=tgt)

        results = []
        for text in texts:
            if not text.strip():
                results.append(text)
                continue
            try:
                marked_text, markers = self._apply_markers(text, glossary)
                translated = translator.translate(marked_text)
                if translated and markers:
                    translated = self._restore_markers(translated, markers)
                results.append(translated)
            except Exception:
                results.append(None)
        return results

    def _apply_markers(self, text: str, glossary: dict[str, str] | None) -> tuple[str, dict[str, str]]:
        if not glossary:
            return text, {}
        markers = {}
        marker_idx = 0
        sorted_terms = sorted(glossary.keys(), key=len, reverse=True)
        for term in sorted_terms:
            target = glossary[term]
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            if pattern.search(text):
                marker = f"XGLOSS{marker_idx}X"
                markers[marker] = target
                text = pattern.sub(marker, text)
                marker_idx += 1
        return text, markers

    def _restore_markers(self, text: str, markers: dict[str, str]) -> str:
        for marker, target in markers.items():
            pattern = re.compile(re.escape(marker), re.IGNORECASE)
            text = pattern.sub(target, text)
        return text

    @staticmethod
    def _normalize_lang(code: str) -> str:
        return code.strip().split("-")[0].split("_")[0].lower()
