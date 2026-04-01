from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from pdf_translator.core.extractor import Element
from pdf_translator.core.translator.base import LANG_NAMES as LANG_NAMES
from pdf_translator.core.translator.base import TranslationBackend as TranslationBackend
from pdf_translator.core.translator.base import build_prompt as build_prompt
from pdf_translator.core.translator.base import parse_response as parse_response
from pdf_translator.core.translator.router import BackendRouter as BackendRouter

logger = logging.getLogger(__name__)


def detect_language(elements: list[Element]) -> str:
    from langdetect import LangDetectException, detect
    text = " ".join(el.content for el in elements if el.content.strip())[:3000]
    if not text.strip():
        return "en"
    try:
        lang = detect(text)
        return lang.split("-")[0]
    except LangDetectException:
        return "en"


def _worker_translate(
    work_item: tuple[list[dict], str, str, str, str, dict[str, str] | None],
) -> list[tuple[int, str, str]]:
    items, source_lang, target_lang, effort, backend_name, glossary = work_item
    uncached = [d for d in items if not d["cached"]]
    if not uncached:
        return []

    router = BackendRouter(effort=effort)
    backend = router.select(backend_name)

    texts = [d["content"] for d in uncached]
    translations = backend.translate(texts, source_lang, target_lang, glossary=glossary)
    return [
        (item["global_idx"], translated, item["content"])
        for item, translated in zip(uncached, translations)
    ]


def translate_all(
    batches: list[list[Element]],
    source_lang: str,
    target_lang: str,
    effort: str = "low",
    workers: int = 4,
    cache=None,
    backend: str = "auto",
    glossary: dict[str, str] | None = None,
) -> dict[int, str]:
    results: dict[int, str] = {}
    work_items = []
    global_idx = 0

    for batch in batches:
        all_cached = True
        batch_items = []
        for el in batch:
            cached_text = cache.get(el.content, source_lang, target_lang) if cache else None
            if cached_text is not None:
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
        if not all_cached:
            work_items.append((batch_items, source_lang, target_lang, effort, backend, glossary))

    if not work_items:
        return results

    workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=min(workers, len(work_items))) as executor:
        for batch_results in executor.map(_worker_translate, work_items):
            for gidx, translated, original in batch_results:
                if translated is not None:
                    results[gidx] = translated
                    if cache:
                        cache.put(original, source_lang, target_lang, translated)
                elif gidx not in results:
                    results[gidx] = original

    return results
