from __future__ import annotations

from pdf_translator.extractor import Element


def build_batches(
    elements: list[Element],
    max_segments: int = 40,
    max_chars: int = 4500,
) -> list[list[Element]]:
    valid = [e for e in elements if e.content.strip()]
    if not valid:
        return []

    batches: list[list[Element]] = []
    current: list[Element] = []
    current_chars = 0

    for el in valid:
        el_chars = len(el.content)
        would_exceed_segments = len(current) >= max_segments
        would_exceed_chars = current_chars + el_chars > max_chars and current

        if would_exceed_segments or would_exceed_chars:
            batches.append(current)
            current = []
            current_chars = 0

        current.append(el)
        current_chars += el_chars

    if current:
        batches.append(current)

    return batches
