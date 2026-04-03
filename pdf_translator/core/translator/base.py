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

    return f"""You are a professional academic translator.
Translate the following text from {src_name} to {tgt_name}.

RULES:
- Translate EVERY word and phrase into {tgt_name}. Nothing should remain in the source language except:
  * Proper nouns (person/company/place names)
  * Model/dataset names (e.g., Transformer, ImageNet, BERT)
  * Widely-known abbreviations (e.g., BLEU, LSTM, API, GPU)
  * Mathematical formulas, equations, and variable names
- This includes common English words like "the", "of", "with", "based", "using", etc. — translate them all.
- Translate ALL technical AND general terms (e.g., "method" → "방법", "performance" → "성능", "approach" → "접근법", "framework" → "프레임워크", "contribution" → "기여").
- "Abstract" → standard academic term (e.g., 초록 in Korean).
- Preserve the original structure and formatting.
- Input is a JSON array of indexed items.
- Output ONLY a JSON array in the same order with translated text.
- Do not merge or split items.{glossary_section}

Input:
{json.dumps(items, ensure_ascii=False)}"""


def build_prompt_with_layout(
    items: list[dict],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
) -> str:
    """Build a translation prompt that includes bbox/type metadata.

    Each item: {"index", "text", "type", "bbox_w", "bbox_h"}
    LLM returns: [{"index", "action": "translate"|"skip", "text": "..."}]
    """
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)

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

    return f"""You are a professional academic translator.
Translate text from {src_name} to {tgt_name}. Each item has a text area size (bbox_w x bbox_h in points).

RULES:
- For each item, decide: "action": "translate" or "action": "skip".
- Set action to "skip" for: mathematical formulas, equations, variable declarations, citation numbers, page numbers.
- Set action to "translate" for: headings, paragraphs, captions, author info, footnotes.
- Translate EVERY word and phrase into {tgt_name}. Nothing should remain in the source language except:
  * Proper nouns (person/company/place names)
  * Model/dataset names (e.g., Transformer, ImageNet, BERT)
  * Widely-known abbreviations (e.g., BLEU, LSTM, API, GPU)
- This includes common English words like "the", "of", "with", "based", "using", etc. — translate them all.
- Translate ALL technical AND general terms (e.g., "method" → "방법", "performance" → "성능", "approach" → "접근법", "framework" → "프레임워크").
- When translating, be aware of the text area size. If the area is small, keep the translation concise.
- "Abstract" at the start of a paper → translate as the standard academic term (e.g., 초록 in Korean).
- Preserve the original structure. Do not merge or split items.
- Output ONLY a JSON array: [{{"index": N, "action": "translate"|"skip", "text": "..."}}]
- For "skip" items, omit the "text" field.{glossary_section}

Input:
{json.dumps(items, ensure_ascii=False)}"""


def parse_response_with_action(response: str, count: int) -> list[dict]:
    """Parse LLM response with action field.

    Returns list of {"action": "translate"|"skip", "text": str|None}.
    Falls back gracefully if LLM returns old format (no action).
    """
    response = response.strip()
    result = [{"action": "skip", "text": None}] * count

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
            for item in data:
                if not isinstance(item, dict):
                    continue
                idx = item.get("index", -1)
                if not (0 <= idx < count):
                    continue
                action = item.get("action", "translate")  # default to translate for backward compat
                text = item.get("text")
                result[idx] = {"action": action, "text": text}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse layout response: %s", exc)

    return result


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


def build_qa_pre_prompt(issues: list[dict], source_lang: str, target_lang: str) -> str:
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)
    return f"""You are a translation quality reviewer ({src_name} → {tgt_name}).

Review each flagged translation issue and decide an action:
- "keep": the current translation is acceptable despite the flag
- "revise": provide a better translation (include "text" field)
- "skip": keep the original text, do not translate this element

Output ONLY a JSON array: [{{"index": N, "action": "keep"|"revise"|"skip", "text": "...", "reason": "..."}}]
For "keep" and "skip", omit "text".

Flagged issues:
{json.dumps(issues, ensure_ascii=False, indent=2)}"""


def build_qa_post_prompt(issues: list[dict]) -> str:
    return f"""You are a PDF translation quality reviewer.

I built a translated PDF but detected potential problems on some pages.
For each page, decide:
- "pass": the page is acceptable
- "fail": the page has problems — list the segment indices that need re-translation in "failed_indices"

Output ONLY a JSON array: [{{"page": N, "verdict": "pass"|"fail", "failed_indices": [...], "reason": "..."}}]

Detected issues:
{json.dumps(issues, ensure_ascii=False, indent=2)}"""


def parse_qa_pre_response(response: str) -> list[dict]:
    """Parse pre-build QA response. Returns list of action dicts."""
    response = response.strip()
    try:
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if fence_match:
            response = fence_match.group(1).strip()
        bracket_start = response.find("[")
        bracket_end = response.rfind("]")
        if bracket_start >= 0 and bracket_end > bracket_start:
            response = response[bracket_start:bracket_end + 1]
        return json.loads(response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse QA pre response: %s", exc)
        return []


def parse_qa_post_response(response: str) -> list[dict]:
    """Parse post-build QA response. Returns list of verdict dicts."""
    response = response.strip()
    try:
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if fence_match:
            response = fence_match.group(1).strip()
        bracket_start = response.find("[")
        bracket_end = response.rfind("]")
        if bracket_start >= 0 and bracket_end > bracket_start:
            response = response[bracket_start:bracket_end + 1]
        return json.loads(response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse QA post response: %s", exc)
        return []
