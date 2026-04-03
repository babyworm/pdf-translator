"""Markdown-based translation pipeline.

Translates paragraphs from cleaned markdown, preserving structure.
"""
from __future__ import annotations

import json
import logging
import re

from pdf_translator.core.translator.base import LANG_NAMES

logger = logging.getLogger(__name__)

# Patterns that should not be translated
_SKIP_PATTERNS = re.compile(
    r'^(?:'
    r'!\[.*?\]\(.*?\)\s*$|'           # image references
    r'\|.*\|.*\|\s*$|'                # table rows (keep as-is for now)
    r'[-:|\s]+$|'                      # table separators
    r'Manuscript received\s|'
    r'This work was supported\s|'
    r'This paper was recommended\s|'
    r'Digital Object Identi|'
    r'[A-Z]\.-[A-Z]\.\s\w+.*(?:are with|is with)\s|'  # author affiliations
    r'[A-Z]+\s+et\s+al\.\s*:|'        # page headers (CHEN et al.:)
    r'\d+\s+IEEE\s|'                   # journal page headers
    r'©|®|™|'
    r'Authorized licensed|'
    r'Downloaded on\s|'
    r'\d+-\d+/\$\d+'                   # copyright line (1051-8215/$25.00)
    r')',
    re.MULTILINE,
)

# Heading pattern
_HEADING = re.compile(r'^(#+)\s+')


def _should_skip(paragraph: str) -> bool:
    """Check if a paragraph should be skipped (not translated)."""
    stripped = paragraph.strip()
    if not stripped:
        return True
    # Skip images
    if stripped.startswith('!['):
        return True
    # Skip pure table content
    if stripped.startswith('|') and stripped.endswith('|'):
        return True
    # Skip decorative/metadata
    if _SKIP_PATTERNS.match(stripped):
        return True
    return False


def build_md_prompt(
    paragraphs: list[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
) -> str:
    """Build translation prompt for markdown paragraphs."""
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)

    items = [{"index": i, "text": p} for i, p in enumerate(paragraphs)]

    glossary_section = ""
    if glossary:
        keep_terms = [k for k, v in glossary.items() if k.lower() == v.lower()]
        translate_terms = [(k, v) for k, v in glossary.items() if k.lower() != v.lower()]
        parts = []
        if keep_terms:
            parts.append(f"Keep these terms as-is (DO NOT translate): {', '.join(keep_terms)}")
        if translate_terms:
            mappings = ", ".join(f"{k} → {v}" for k, v in translate_terms)
            parts.append(f"Use these translations: {mappings}")
        glossary_section = "\n\nGLOSSARY RULES:\n" + "\n".join(f"- {p}" for p in parts)

    return f"""You are a professional academic translator.
Translate the following text from {src_name} to {tgt_name}.

RULES:
- Translate EVERY word and phrase into {tgt_name}. Nothing should remain in the source language except:
  * Proper nouns (person/company/place names)
  * Model/dataset names (e.g., Transformer, ImageNet, BERT)
  * Widely-known abbreviations (e.g., BLEU, LSTM, API, GPU)
  * Mathematical formulas, equations, and variable names
- This includes common English words like "the", "of", "with", "based", "using", etc. — translate them all.
- Translate ALL technical AND general terms (e.g., "method" → "방법", "performance" → "성능", "approach" → "접근법").
- Preserve markdown formatting (headings with #, bold, italic, etc.).
- "Abstract" → standard academic term (e.g., 초록 in Korean).
- Input is a JSON array of indexed items.
- Output ONLY a JSON array in the same order with translated text.
- Do not merge or split items.{glossary_section}

Input:
{json.dumps(items, ensure_ascii=False)}"""


def translate_markdown(
    paragraphs: list[str],
    source_lang: str,
    target_lang: str,
    backend: str = "auto",
    effort: str = "low",
    workers: int = 4,
    glossary: dict[str, str] | None = None,
    use_cache: bool = True,
    output_dir: str = "./output",
) -> str:
    """Translate paragraphs and reconstruct markdown.

    Returns the translated markdown string.
    """
    from pathlib import Path

    from pdf_translator.core.cache import TranslationCache
    from pdf_translator.core.extractor import Element
    from pdf_translator.core.translator import translate_all

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Separate translatable vs skip paragraphs
    to_translate: list[tuple[int, str]] = []
    for i, p in enumerate(paragraphs):
        if not _should_skip(p):
            to_translate.append((i, p))

    if not to_translate:
        return "\n\n".join(paragraphs)

    # Convert to Element objects for the existing translation pipeline
    elements = [
        Element(
            type="paragraph",
            content=text,
            page_number=idx,  # use index as page for tracking
            bbox=[0, 0, 500, 20],
        )
        for idx, text in to_translate
    ]

    # Build batches manually (simple char-based splitting)
    max_chars = 4500
    batches: list[list[Element]] = []
    current: list[Element] = []
    current_chars = 0
    for el in elements:
        el_chars = len(el.content)
        if current_chars + el_chars > max_chars and current:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(el)
        current_chars += el_chars
    if current:
        batches.append(current)

    # Translate
    cache = TranslationCache(output_path / "cache.db") if use_cache else None
    try:
        raw_translations = translate_all(
            batches,
            source_lang=source_lang,
            target_lang=target_lang,
            effort=effort,
            workers=workers,
            cache=cache,
            backend=backend,
            glossary=glossary,
        )
    finally:
        if cache:
            cache.flush()
            cache.close()

    # Map translations back
    translated = list(paragraphs)  # copy
    for batch_idx, text in raw_translations.items():
        if batch_idx < len(to_translate) and text:
            orig_idx = to_translate[batch_idx][0]
            # Preserve heading prefix if present
            orig = paragraphs[orig_idx]
            heading_match = _HEADING.match(orig)
            if heading_match and not _HEADING.match(text):
                text = f"{heading_match.group(0)}{text}"
            translated[orig_idx] = text

    return "\n\n".join(translated)
