"""Tests for translate_all with cache integration and index mapping."""
import json
from unittest.mock import patch, MagicMock
from pdf_translator.core.extractor import Element
from pdf_translator.core.cache import TranslationCache
from pdf_translator.core.translator import translate_all


def _el(content: str, page: int = 1) -> Element:
    return Element(
        type="paragraph", content=content, page_number=page,
        bbox=[0, 0, 100, 20],
    )


def _mock_worker(work_item):
    """In-process worker that returns mock translations."""
    items, src, tgt, effort, backend_name = work_item
    return [
        (item["global_idx"], f"[{tgt}]{item['content']}", item["content"])
        for item in items
        if not item["cached"]
    ]


def test_translate_all_no_cache():
    batches = [[_el("Hello"), _el("World")]]

    with patch("pdf_translator.core.translator._worker_translate", side_effect=_mock_worker):
        with patch("pdf_translator.core.translator.Pool") as MockPool:
            pool_inst = MockPool.return_value.__enter__.return_value
            pool_inst.map.side_effect = lambda fn, items: [fn(i) for i in items]

            results = translate_all(batches, "en", "ko", workers=1)

    assert results[0] == "[ko]Hello"
    assert results[1] == "[ko]World"


def test_translate_all_full_cache_hit():
    """When all items are cached, no codex call should happen."""
    cache = MagicMock()
    cache.get.return_value = "캐시됨"

    batches = [[_el("Hello"), _el("World")]]
    results = translate_all(batches, "en", "ko", workers=1, cache=cache)

    assert results[0] == "캐시됨"
    assert results[1] == "캐시됨"
    cache.put.assert_not_called()


def test_translate_all_partial_cache():
    """Partial cache: entire batch sent to codex (preserves context)."""
    cache = MagicMock()
    cache.get.side_effect = lambda content, src, tgt: "캐시됨" if content == "Hello" else None

    batches = [[_el("Hello"), _el("World")]]

    with patch("pdf_translator.core.translator._worker_translate", side_effect=_mock_worker):
        with patch("pdf_translator.core.translator.Pool") as MockPool:
            pool_inst = MockPool.return_value.__enter__.return_value
            pool_inst.map.side_effect = lambda fn, items: [fn(i) for i in items]

            results = translate_all(batches, "en", "ko", workers=1, cache=cache)

    # Both should have results (cached item keeps cache value)
    assert 0 in results
    assert 1 in results


def test_translate_all_preserves_global_indices():
    """Multiple batches should maintain correct global indices."""
    batches = [[_el("A"), _el("B")], [_el("C")]]

    with patch("pdf_translator.core.translator._worker_translate", side_effect=_mock_worker):
        with patch("pdf_translator.core.translator.Pool") as MockPool:
            pool_inst = MockPool.return_value.__enter__.return_value
            pool_inst.map.side_effect = lambda fn, items: [fn(i) for i in items]

            results = translate_all(batches, "en", "ko", workers=1)

    assert results[0] == "[ko]A"
    assert results[1] == "[ko]B"
    assert results[2] == "[ko]C"


def test_translate_all_empty_batches():
    results = translate_all([], "en", "ko", workers=1)
    assert results == {}
