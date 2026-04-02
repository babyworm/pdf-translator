from __future__ import annotations

import logging

from pypdf import PdfReader

from pdf_translator.core.extractor import Element

logger = logging.getLogger(__name__)


def _estimate_text_width(text: str, font_size: float) -> float:
    """Rough estimate of text width in points."""
    return sum(font_size * (1.0 if ord(ch) > 0x2E80 else 0.6) for ch in text)


def detect_pre_build_issues(
    elements: list[Element],
    translations: dict[int, str],
) -> list[dict]:
    """Detect potential layout issues before PDF build. No LLM calls."""
    issues = []

    for i, el in enumerate(elements):
        if i not in translations:
            continue
        translated = translations[i]
        bbox = el.bbox
        if not bbox or len(bbox) != 4:
            continue

        bbox_w = bbox[2] - bbox[0]
        bbox_h = bbox[3] - bbox[1]
        original = el.content

        # Empty translation
        if not translated or not translated.strip():
            issues.append({
                "index": i, "original": original, "translated": translated,
                "type": el.type, "bbox_w": round(bbox_w, 1), "bbox_h": round(bbox_h, 1),
                "issue": "empty translation",
            })
            continue

        # Identical to original (translation may have failed)
        if translated.strip() == original.strip():
            issues.append({
                "index": i, "original": original, "translated": translated,
                "type": el.type, "bbox_w": round(bbox_w, 1), "bbox_h": round(bbox_h, 1),
                "issue": "identical to original — possible translation failure",
            })
            continue

        # Overflow risk: translated text much longer and bbox is small
        est_width = _estimate_text_width(translated, el.font_size)
        num_lines = max(1, est_width / bbox_w) if bbox_w > 0 else 1
        est_height = num_lines * el.font_size * 1.3

        if len(translated) > len(original) * 2 and est_height > bbox_h * 2:
            issues.append({
                "index": i, "original": original, "translated": translated,
                "type": el.type, "bbox_w": round(bbox_w, 1), "bbox_h": round(bbox_h, 1),
                "issue": "translated text likely overflows bbox",
            })
            continue

        # Heading overflow
        if el.type == "heading" and est_width > bbox_w * 1.5:
            issues.append({
                "index": i, "original": original, "translated": translated,
                "type": el.type, "bbox_w": round(bbox_w, 1), "bbox_h": round(bbox_h, 1),
                "issue": "heading overflow — translation exceeds 150% of bbox width",
            })

    return issues


def detect_post_build_issues(
    src_pdf: str,
    built_pdf: str,
    elements: list[Element],
    translations: dict[int, str],
) -> list[dict]:
    """Detect issues in the built PDF by re-extracting text. No LLM calls."""
    issues = []

    try:
        reader = PdfReader(built_pdf)
    except Exception as e:
        logger.warning("Cannot read built PDF for QA: %s", e)
        return issues

    # Group expected translations by page
    by_page: dict[int, list[tuple[int, str, str]]] = {}
    for i, el in enumerate(elements):
        if i in translations:
            by_page.setdefault(el.page_number, []).append(
                (i, el.content, translations[i])
            )

    for page_num, expected in by_page.items():
        page_idx = page_num - 1
        if page_idx < 0 or page_idx >= len(reader.pages):
            issues.append({
                "page": page_num,
                "expected_segments": len(expected),
                "extracted_text": "",
                "original_text": "",
                "issues": [f"page {page_num} not found in built PDF"],
            })
            continue

        extracted = reader.pages[page_idx].extract_text() or ""

        page_issues = []

        # Check if expected translated segments appear
        found = sum(1 for _, _, trans in expected if trans[:10] in extracted)
        if found < len(expected) * 0.5:
            page_issues.append(
                f"only {found} of {len(expected)} segments found in extracted text"
            )

        # Check if original text still visible
        original_found = sum(
            1 for _, orig, _ in expected
            if len(orig) > 10 and orig[:15] in extracted
        )
        if original_found > 0:
            page_issues.append(
                f"{original_found} original text segments still visible"
            )

        if page_issues:
            originals = " | ".join(orig[:30] for _, orig, _ in expected[:3])
            issues.append({
                "page": page_num,
                "expected_segments": len(expected),
                "extracted_text": extracted[:500],
                "original_text": originals,
                "issues": page_issues,
            })

    return issues
