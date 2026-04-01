# pdf_translator/core/translator/base.py
from __future__ import annotations

import json
import logging
import re
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

LANG_NAMES = {
    "en": "English", "ko": "Korean", "ja": "Japanese",
    "zh": "Chinese", "de": "German", "fr": "French",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian",
}


@runtime_checkable
class TranslationBackend(Protocol):
    name: str
    backend_type: str

    def is_available(self) -> bool: ...

    def translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        glossary: dict[str, str] | None = None,
    ) -> list[str | None]: ...


def build_prompt(
    texts: list[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
) -> str:
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)
    items = [{"index": i, "text": t} for i, t in enumerate(texts)]

    glossary_section = ""
    if glossary:
        keep_terms = [k for k, v in glossary.items() if k.lower() == v.lower()]
        translate_terms = [(k, v) for k, v in glossary.items() if k.lower() != v.lower()]
        parts = []
        if keep_terms:
            parts.append(f"Keep these terms as-is (DO NOT translate): {', '.join(keep_terms)}")
        if translate_terms:
            mappings = ", ".join(f"{k} → {v}" for k, v in translate_terms)
            parts.append(f"Use these translations: {mappings}")
        glossary_section = "\n\nGLOSSARY RULES:\n" + "\n".join(f"- {p}" for p in parts)

    return f"""You are a professional translator.
Translate the following text from {src_name} to {tgt_name}.
Preserve the original structure and formatting.
Input is a JSON array of indexed items.
Output ONLY a JSON array in the same order with translated text.
Do not merge or split items. Keep untranslatable terms as-is.{glossary_section}

Input:
{json.dumps(items, ensure_ascii=False)}"""


def parse_response(response: str, count: int) -> list[str | None]:
    response = response.strip()
    try:
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if fence_match:
            response = fence_match.group(1).strip()

        bracket_start = response.find("[")
        bracket_end = response.rfind("]")
        if bracket_start >= 0 and bracket_end > bracket_start:
            response = response[bracket_start:bracket_end + 1]

        data = json.loads(response)
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                result = [None] * count
                for item in data:
                    idx = item.get("index", -1)
                    text = item.get("text", "")
                    if 0 <= idx < count and text:
                        result[idx] = text
                missing = sum(1 for r in result if r is None)
                if missing:
                    logger.warning("Response missing %d/%d items", missing, count)
                return result
            result = [str(item) if item else None for item in data]
            if len(result) < count:
                logger.warning("Response has %d items, expected %d", len(result), count)
            while len(result) < count:
                result.append(None)
            return result[:count]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse response: %s", exc)

    lines = [line.strip() for line in response.strip().split("\n") if line.strip()]
    if len(lines) >= count:
        return lines[:count]
    return lines + [None] * (count - len(lines))
