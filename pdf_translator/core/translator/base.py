from __future__ import annotations
import json
import logging

logger = logging.getLogger(__name__)

LANG_NAMES = {
    "en": "English", "ko": "Korean", "ja": "Japanese",
    "zh": "Chinese", "de": "German", "fr": "French",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian",
}


def build_prompt(
    texts: list[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
) -> str:
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)
    items = [{"index": i, "text": t} for i, t in enumerate(texts)]

    glossary_block = ""
    if glossary:
        glossary_block = (
            "\n\nGlossary (use these translations for the given terms):\n"
            + json.dumps(glossary, ensure_ascii=False)
        )

    return f"""You are a professional translator.
Translate the following text from {src_name} to {tgt_name}.
Preserve the original structure and formatting.
Input is a JSON array of indexed items.
Output ONLY a JSON array in the same order with translated text.
Do not merge or split items. Keep untranslatable terms as-is.
{glossary_block}
Input:
{json.dumps(items, ensure_ascii=False)}"""


def parse_response(response: str, count: int) -> list[str | None]:
    response = response.strip()
    try:
        import re
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
                return result
            result = [str(item) if item else None for item in data]
            while len(result) < count:
                result.append(None)
            return result[:count]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
    if len(lines) >= count:
        return lines[:count]

    return lines + [None] * (count - len(lines))
