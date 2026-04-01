from pdf_translator.core.extractor import Element
from pdf_translator.core.chunker import build_batches

def _el(content: str, page: int = 1) -> Element:
    return Element(
        type="paragraph", content=content, page_number=page,
        bbox=[0, 0, 100, 20],
    )

def test_single_batch():
    elements = [_el("Hello"), _el("World")]
    batches = build_batches(elements)
    assert len(batches) == 1
    assert len(batches[0]) == 2


def test_split_by_count():
    elements = [_el(f"item {i}") for i in range(50)]
    batches = build_batches(elements, max_segments=40)
    assert len(batches) == 2
    assert len(batches[0]) == 40
    assert len(batches[1]) == 10


def test_split_by_chars():
    elements = [_el("a" * 2000) for _ in range(5)]
    batches = build_batches(elements, max_chars=4500)
    assert len(batches) >= 3


def test_empty_input():
    assert build_batches([]) == []


def test_skips_empty_content():
    elements = [_el(""), _el("real text"), _el("   ")]
    batches = build_batches(elements)
    assert len(batches) == 1
    assert len(batches[0]) == 1
