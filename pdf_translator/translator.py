from __future__ import annotations

import json
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
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(
                l for l in lines if not l.startswith("```")
            )

        data = json.loads(response)
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                sorted_items = sorted(data, key=lambda x: x.get("index", 0))
                return [item.get("text", "") for item in sorted_items]
            return [str(item) for item in data]
    except (json.JSONDecodeError, KeyError):
        pass

    lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
    if len(lines) >= count:
        return lines[:count]

    return lines + [""] * (count - len(lines))


def _run_codex(prompt: str, effort: str, max_retries: int = 2) -> str:
    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(
                ["codex", "exec", "-s", "read-only", "--effort", effort, prompt],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            if attempt < max_retries:
                time.sleep(min(0.5 * (2 ** attempt), 4.0))
        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                time.sleep(min(0.5 * (2 ** attempt), 4.0))

    return ""


def translate_batch(
    batch: list[Element],
    source_lang: str,
    target_lang: str,
    effort: str = "low",
) -> list[str]:
    prompt = build_prompt(batch, source_lang, target_lang)
    response = _run_codex(prompt, effort)
    if not response:
        return [el.content for el in batch]
    return parse_codex_response(response, count=len(batch))


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
        batch_items: list[dict] = []
        for el in batch:
            if cache:
                cached = cache.get(el.content, source_lang, target_lang)
                if cached:
                    results[global_idx] = cached
                    global_idx += 1
                    continue
            batch_items.append({
                "type": el.type, "content": el.content,
                "page_number": el.page_number, "bbox": el.bbox,
                "global_idx": global_idx,
            })
            global_idx += 1
        if batch_items:
            work_items.append((batch_items, source_lang, target_lang, effort))

    if not work_items:
        return results

    with Pool(processes=min(workers, len(work_items))) as pool:
        for batch_results in pool.map(_worker_translate, work_items):
            for gidx, translated, original in batch_results:
                results[gidx] = translated
                if cache:
                    cache.put(original, source_lang, target_lang, translated)

    return results
