from __future__ import annotations

import logging

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
                translated = translator.translate(text)
                if glossary and translated:
                    for src_term, tgt_term in glossary.items():
                        if src_term.lower() != tgt_term.lower():
                            translated = translated.replace(src_term, tgt_term)
                results.append(translated)
            except Exception:
                results.append(None)
        return results

    @staticmethod
    def _normalize_lang(code: str) -> str:
        return code.strip().split("-")[0].split("_")[0].lower()
