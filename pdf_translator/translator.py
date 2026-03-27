from __future__ import annotations

import json
import shutil
import subprocess
import time
from multiprocessing import Pool
from functools import partial

from pdf_translator.extractor import Element


LANG_NAMES = {
    "en": "English", "ko": "Korean", "ja": "Japanese",
    "zh": "Chinese", "de": "German", "fr": "French",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian",
}

# Google Translate uses slightly different codes for some languages
_GOOGLE_LANG_MAP = {
    "zh": "zh-CN",
}

_codex_available: bool | None = None


def is_codex_available() -> bool:
    global _codex_available
    if _codex_available is None:
        _codex_available = shutil.which("codex") is not None
    return _codex_available


def detect_language(elements: list[Element]) -> str:
    """Detect source language from extracted elements."""
    from langdetect import detect, LangDetectException

    text = " ".join(el.content for el in elements if el.content.strip())[:3000]
    if not text.strip():
        return "en"
    try:
        lang = detect(text)
        return lang.split("-")[0]  # normalize 'zh-cn' -> 'zh'
    except LangDetectException:
        return "en"


def build_prompt(batch: list[Element], source_lang: str, target_lang: str) -> str:
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)
    items = [{"index": i, "text": el.content} for i, el in enumerate(batch)]

    return f"""You are a professional translator.
Translate the following text from {src_name} to {tgt_name}.
Preserve the original structure and formatting.
Input is a JSON array of indexed items.
Output ONLY a JSON array in the same order with translated text.
Do not merge or split items. Keep untranslatable terms as-is.

Input:
{json.dumps(items, ensure_ascii=False)}"""


def parse_codex_response(response: str, count: int) -> list[str]:
    response = response.strip()

    try:
        # Strip code fences anywhere in response
        import re
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if fence_match:
            response = fence_match.group(1).strip()

        # Try to extract JSON array from anywhere in the response
        bracket_start = response.find("[")
        bracket_end = response.rfind("]")
        if bracket_start >= 0 and bracket_end > bracket_start:
            response = response[bracket_start:bracket_end + 1]

        data = json.loads(response)
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                # Map by explicit index into fixed-size result array
                result = [None] * count
                for item in data:
                    idx = item.get("index", -1)
                    text = item.get("text", "")
                    if 0 <= idx < count and text:
                        result[idx] = text
                return result
            result = [str(item) if item else None for item in data]
            # Pad to exact count
            while len(result) < count:
                result.append(None)
            return result[:count]
    except (json.JSONDecodeError, KeyError):
        pass

    lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
    if len(lines) >= count:
        return lines[:count]

    # Pad with None (failure) for missing items
    return lines + [None] * (count - len(lines))


def _run_codex(prompt: str, effort: str, max_retries: int = 2) -> str:
    for attempt in range(max_retries + 1):
        try:
            import tempfile, os
            out_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, prefix="codex_out_",
            )
            out_path = out_file.name
            out_file.close()

            cmd = ["codex", "exec", "-s", "read-only", "-o", out_path]
            if effort:
                cmd += ["-c", f"reasoning_effort={effort}"]
            cmd.append(prompt)
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and os.path.exists(out_path):
                with open(out_path, encoding="utf-8") as f:
                    content = f.read().strip()
                os.unlink(out_path)
                if content:
                    return content
            else:
                os.unlink(out_path) if os.path.exists(out_path) else None

            if attempt < max_retries:
                time.sleep(min(0.5 * (2 ** attempt), 4.0))
        except subprocess.TimeoutExpired:
            os.unlink(out_path) if os.path.exists(out_path) else None
            if attempt < max_retries:
                time.sleep(min(0.5 * (2 ** attempt), 4.0))

    return ""


def _translate_batch_google(
    batch: list[Element], source_lang: str, target_lang: str,
) -> list[str | None]:
    """Translate a batch using Google Translate (fallback)."""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        return [None] * len(batch)

    src = _GOOGLE_LANG_MAP.get(source_lang, source_lang)
    tgt = _GOOGLE_LANG_MAP.get(target_lang, target_lang)
    translator = GoogleTranslator(source=src, target=tgt)

    results: list[str | None] = []
    for el in batch:
        if not el.content.strip():
            results.append(el.content)
            continue
        try:
            results.append(translator.translate(el.content))
        except Exception:
            results.append(None)
    return results


def translate_batch(
    batch: list[Element],
    source_lang: str,
    target_lang: str,
    effort: str = "low",
) -> list[str | None]:
    """Translate a batch. Uses Codex CLI if available, otherwise Google Translate."""
    if is_codex_available():
        prompt = build_prompt(batch, source_lang, target_lang)
        response = _run_codex(prompt, effort)
        if not response:
            return [None] * len(batch)
        return parse_codex_response(response, count=len(batch))
    return _translate_batch_google(batch, source_lang, target_lang)


def _worker_translate(
    work_item: tuple[list[dict], str, str, str],
) -> list[tuple[int, str, str]]:
    items, source_lang, target_lang, effort = work_item
    elements = [
        Element(
            type=d["type"], content=d["content"], page_number=d["page_number"],
            bbox=d["bbox"],
        )
        for d in items
    ]
    translations = translate_batch(elements, source_lang, target_lang, effort)
    return [
        (item["global_idx"], translated, item["content"])
        for item, translated in zip(items, translations)
    ]


def translate_all(
    batches: list[list[Element]],
    source_lang: str,
    target_lang: str,
    effort: str = "low",
    workers: int = 4,
    cache=None,
) -> dict[int, str]:
    results: dict[int, str] = {}
    work_items: list[tuple[list[dict], str, str, str]] = []
    global_idx = 0

    for batch in batches:
        all_cached = True
        batch_items: list[dict] = []
        for el in batch:
            cached_text = cache.get(el.content, source_lang, target_lang) if cache else None
            if cached_text:
                results[global_idx] = cached_text
            else:
                all_cached = False
            batch_items.append({
                "type": el.type, "content": el.content,
                "page_number": el.page_number, "bbox": el.bbox,
                "global_idx": global_idx,
                "cached": cached_text is not None,
            })
            global_idx += 1
        # Send entire batch to codex if any item is uncached (preserve context)
        if not all_cached:
            work_items.append((batch_items, source_lang, target_lang, effort))

    if not work_items:
        return results

    workers = max(1, workers)
    with Pool(processes=min(workers, len(work_items))) as pool:
        for batch_results in pool.map(_worker_translate, work_items):
            for gidx, translated, original in batch_results:
                if translated is not None:
                    results[gidx] = translated
                    if cache:
                        cache.put(original, source_lang, target_lang, translated)
                elif gidx not in results:
                    # Codex failed and no cache hit: fallback to original
                    results[gidx] = original

    return results
