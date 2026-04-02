from __future__ import annotations

import re

from pdf_translator.core.extractor import Element

_MATH_PATTERN = re.compile(
    r"[=∑∫∏∂∇±×÷√∞≈≠≤≥∈∉⊂⊃∀∃∧∨¬⟨⟩‖αβγδεζηθλμσφψω]"
)


def is_math(text: str) -> bool:
    """Detect if text is likely a mathematical formula (not prose with math mentions)."""
    stripped = text.strip()
    if not stripped:
        return False
    # Long text is almost certainly prose, not a formula
    if len(stripped) > 80:
        return False
    # Unicode math symbols (strong signal)
    symbol_count = len(_MATH_PATTERN.findall(stripped))
    if symbol_count >= 2:
        return True
    # Mostly non-letter characters (numbers, operators, parens)
    alpha_count = sum(1 for c in stripped if c.isalpha())
    if len(stripped) > 3 and alpha_count / len(stripped) < 0.3:
        return True
    # Function/equation pattern: "Name(args) = ..." short formula definitions
    if "=" in stripped and "(" in stripped and len(stripped) < 60:
        paren_count = stripped.count("(") + stripped.count(")")
        comma_count = stripped.count(",")
        if paren_count >= 2 and (comma_count >= 1 or symbol_count >= 1):
            return True
    return False


def build_batches(
    elements: list[Element],
    max_segments: int = 40,
    max_chars: int = 4500,
) -> list[list[Element]]:
    valid = [e for e in elements if e.content.strip() and not is_math(e.content)]
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
