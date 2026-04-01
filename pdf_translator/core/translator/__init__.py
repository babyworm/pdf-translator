from __future__ import annotations

import logging
from multiprocessing import Pool

from pdf_translator.core.extractor import Element
from pdf_translator.core.translator.base import TranslationBackend, build_prompt, parse_response, LANG_NAMES
from pdf_translator.core.translator.router import BackendRouter

logger = logging.getLogger(__name__)


def detect_language(elements: list[Element]) -> str:
    from langdetect import detect, LangDetectException
    text = " ".join(el.content for el in elements if el.content.strip())[:3000]
    if not text.strip():
        return "en"
    try:
        lang = detect(text)
        return lang.split("-")[0]
    except LangDetectException:
        return "en"


def _worker_translate(
    work_item: tuple[list[dict], str, str, str, str],
) -> list[tuple[int, str, str]]:
    items, source_lang, target_lang, effort, backend_name = work_item
    uncached = [d for d in items if not d["cached"]]
    if not uncached:
        return []

    router = BackendRouter(effort=effort)
    backend = router.select(backend_name)

    texts = [d["content"] for d in uncached]
    translations = backend.translate(texts, source_lang, target_lang)
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
            work_items.append((batch_items, source_lang, target_lang, effort, backend))

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
                    results[gidx] = original

    return results
