"""PDF Translator core library -- public API."""
from __future__ import annotations

from pathlib import Path

from pdf_translator.core.cache import TranslationCache as TranslationCache
from pdf_translator.core.chunker import build_batches as build_batches
from pdf_translator.core.config import TranslatorConfig as TranslatorConfig
from pdf_translator.core.extractor import Element as Element
from pdf_translator.core.extractor import extract_pdf as extract_pdf
from pdf_translator.core.glossary import load_glossary as load_glossary
from pdf_translator.core.md_builder import build_markdown as build_markdown
from pdf_translator.core.pdf_builder import build_pdf as build_pdf
from pdf_translator.core.translator import detect_language as detect_language
from pdf_translator.core.translator import translate_all as translate_all
from pdf_translator.core.translator.router import BackendRouter as BackendRouter


def translate_pdf(
    input_path: str,
    target_lang: str = "ko",
    source_lang: str = "auto",
    backend: str = "auto",
    effort: str = "low",
    workers: int = 4,
    output_dir: str = "./output",
    use_cache: bool = True,
    pages: str | None = None,
    glossary: str | dict | None = None,
) -> dict:
    """Translate a PDF file and produce translated PDF + Markdown outputs.

    Returns a dict with keys: pdf_path, md_path, segments_total, segments_translated.
    """
    input_p = Path(input_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_p.stem

    elements = extract_pdf(str(input_p), output_dir=str(out_dir), pages=pages)

    if source_lang == "auto" and elements:
        source_lang = detect_language(elements)

    # Resolve glossary to a dict for the translation pipeline
    glossary_dict = None
    if glossary is not None:
        if isinstance(glossary, dict):
            glossary_dict = glossary
        else:
            g = load_glossary(glossary)
            if g:
                glossary_dict = g.to_prompt_dict()

    valid_indices = [i for i, el in enumerate(elements) if el.content.strip()]
    batches = build_batches(elements)

    cache = TranslationCache(out_dir / "cache.db") if use_cache else None
    try:
        raw = translate_all(
            batches, source_lang=source_lang, target_lang=target_lang,
            effort=effort, workers=workers, cache=cache, backend=backend,
            glossary=glossary_dict,
        )
        translations = {
            valid_indices[gi]: text
            for gi, text in raw.items()
            if gi < len(valid_indices)
        }
    finally:
        if cache:
            cache.flush()
            cache.close()

    pdf_out = str(out_dir / f"{stem}_translated.pdf")
    build_pdf(str(input_p), pdf_out, elements, translations)

    md_out = out_dir / f"{stem}_translated.md"
    md_content = build_markdown(elements, translations)
    md_out.write_text(md_content, encoding="utf-8")

    return {
        "pdf_path": pdf_out,
        "md_path": str(md_out),
        "segments_total": len(elements),
        "segments_translated": len(translations),
    }
