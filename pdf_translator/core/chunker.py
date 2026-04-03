from __future__ import annotations

import re
from copy import deepcopy

from pdf_translator.core.extractor import Element

# Symbols that need 2+ occurrences to signal math
_MATH_WEAK = re.compile(r"[=±×÷⟨⟩‖]")
# Symbols where even 1 occurrence strongly signals math
_MATH_STRONG = re.compile(r"[∑∫∏∂∇√∞≈≠≤≥∈∉⊂⊃∀∃∧∨¬αβγδεζηθλμσφψω]")

# Sentence-ending punctuation (including CJK fullwidth variants)
_SENTENCE_END = re.compile(r'[.!?;:。！？；：…]\s*$')

# Patterns that indicate non-prose elements to skip during merging
_SKIP_PATTERN = re.compile(
    r'^\s*(?:'
    r'©|®|™|All [Rr]ights [Rr]eserved|'
    r'[Ll]icen[cs]|[Cc]opyright|'
    r'ISSN|ISBN|DOI\s*:|'
    r'[Pp]ermission|[Dd]istribut'
    r')',
)

# Decorative / positional elements: skip translation to preserve layout
_NO_TRANSLATE = re.compile(
    r'^\s*(?:'
    r'©|®|™|All [Rr]ights [Rr]eserved|'
    r'[Ll]icen[cs]e|[Cc]opyright|'
    r'ISSN\s|ISBN\s|DOI\s*:|'
    r'[Pp]ermission\s|[Dd]istributed\s|'
    r'[Vv]ol\.\s*\d|[Nn]o\.\s*\d|pp\.\s*\d|'
    r'Authorized licensed use limited to|'
    r'Downloaded on\s'
    r')',
)


def _is_new_paragraph(prev: Element, nxt: Element) -> bool:
    """Heuristic: does nxt start a new paragraph relative to prev?

    Uses vertical gap between bboxes — if the gap is significantly larger
    than the font/line height, it's likely a paragraph break.
    """
    if not prev.bbox or not nxt.bbox or len(prev.bbox) < 4 or len(nxt.bbox) < 4:
        return False
    # bbox format: [x0, y0, x1, y1] — y increases downward in PDF coordinates
    prev_height = abs(prev.bbox[3] - prev.bbox[1])
    line_height = max(prev_height, prev.font_size * 1.3, 10)
    # Vertical gap between bottom of prev and top of nxt
    gap = abs(nxt.bbox[1] - prev.bbox[3])
    # If gap > 1.8x line height, likely a new paragraph
    if gap > line_height * 1.8:
        return True
    return False


def merge_split_sentences(elements: list[Element]) -> list[Element]:
    """Merge elements where a sentence is split across element boundaries.

    When an element does not end with sentence-ending punctuation and the next
    prose element continues the sentence, merge them into one element.
    License/copyright lines between them are skipped (left as separate elements).
    A large vertical gap between elements signals a paragraph break and stops merging.
    """
    if not elements:
        return elements

    result: list[Element] = []
    i = 0
    while i < len(elements):
        el = deepcopy(elements[i])

        # Only attempt merging for paragraph-like prose elements
        if el.type not in ("paragraph", "caption", "list item") or is_math(el.content):
            result.append(el)
            i += 1
            continue

        text = el.content.rstrip()
        # Keep merging while current text doesn't end with sentence punctuation.
        # Skip over interstitial elements (license, footnotes, math, etc.)
        # and reconnect sentence fragments on either side.
        skipped: list[Element] = []
        while not _SENTENCE_END.search(text) and i + 1 < len(elements):
            nxt = elements[i + 1]
            # Hard stop: headings or distant pages break the sentence
            if nxt.type in ("heading",):
                break
            if abs(nxt.page_number - el.page_number) > 1:
                break
            # Interstitial elements: accumulate but don't merge
            if (_SKIP_PATTERN.search(nxt.content) or is_math(nxt.content)
                    or nxt.type not in ("paragraph", "caption", "list item")):
                skipped.append(deepcopy(nxt))
                i += 1
                continue
            # Paragraph break: large vertical gap signals a new paragraph
            if _is_new_paragraph(el, nxt):
                break
            # Merge prose fragment
            el.content = text + " " + nxt.content.lstrip()
            if el.bbox and nxt.bbox and len(el.bbox) >= 4 and len(nxt.bbox) >= 4:
                el.bbox = [
                    min(el.bbox[0], nxt.bbox[0]),
                    min(el.bbox[1], nxt.bbox[1]),
                    max(el.bbox[2], nxt.bbox[2]),
                    max(el.bbox[3], nxt.bbox[3]),
                ]
            text = el.content.rstrip()
            i += 1

        result.append(el)
        result.extend(skipped)
        i += 1

    return result


def is_math(text: str) -> bool:
    """Detect if text is likely a mathematical formula (not prose with math mentions)."""
    stripped = text.strip()
    if not stripped:
        return False
    # Long text is almost certainly prose, not a formula
    if len(stripped) > 80:
        return False
    # Strong math symbols — 1 is enough for short text
    if _MATH_STRONG.search(stripped):
        return True
    # Weak math symbols — need 2+
    weak_count = len(_MATH_WEAK.findall(stripped))
    if weak_count >= 2:
        return True
    # Mostly non-letter characters (numbers, operators, parens)
    alpha_count = sum(1 for c in stripped if c.isalpha())
    if len(stripped) > 3 and alpha_count / len(stripped) < 0.3:
        return True
    # Function/equation pattern: "Name(args) = ..." short formula definitions
    if "=" in stripped and "(" in stripped and len(stripped) < 60:
        paren_count = stripped.count("(") + stripped.count(")")
        comma_count = stripped.count(",")
        if paren_count >= 2 and (comma_count >= 1 or weak_count >= 1):
            return True
    return False


# Heading patterns that mark the start of a non-translatable section
_REFERENCES_HEADING = re.compile(
    r'^\s*(?:References|Bibliography|REFERENCES|BIBLIOGRAPHY|참고\s*문헌)\s*$'
)


def _truncate_at_references(elements: list[Element]) -> list[Element]:
    """Remove elements from the References section onward."""
    for i, el in enumerate(elements):
        if el.type == "heading" and _REFERENCES_HEADING.match(el.content.strip()):
            return elements[:i]
    return elements


def build_batches(
    elements: list[Element],
    max_segments: int = 40,
    max_chars: int = 4500,
) -> list[list[Element]]:
    merged = merge_split_sentences(elements)
    merged = _truncate_at_references(merged)
    valid = [
        e for e in merged
        if e.content.strip()
        and not is_math(e.content)
        and not _NO_TRANSLATE.search(e.content)
    ]
    if not valid:
        return []

    batches: list[list[Element]] = []
    current: list[Element] = []
    current_chars = 0

    import logging
    logger = logging.getLogger(__name__)

    for el in valid:
        el_chars = len(el.content)
        if el_chars > max_chars:
            logger.warning(
                "Element exceeds max_chars (%d > %d), sending as solo batch",
                el_chars, max_chars,
            )
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
