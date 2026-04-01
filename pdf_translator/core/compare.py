from __future__ import annotations

import json
from dataclasses import dataclass

from pdf_translator.core.translator.router import BackendRouter


@dataclass
class ComparisonResult:
    original: str
    translations: dict[str, str | None]  # backend_name -> translation


def compare_backends(
    texts: list[str],
    source_lang: str,
    target_lang: str,
    backends: list[str] | None = None,
    glossary: dict[str, str] | None = None,
) -> list[ComparisonResult]:
    """Translate texts with multiple backends and return comparisons."""
    router = BackendRouter()

    if backends is None:
        backends = router.list_available()

    results = []
    backend_translations: dict[str, list[str | None]] = {}

    for backend_name in backends:
        try:
            backend = router.select(backend_name)
            translated = backend.translate(texts, source_lang, target_lang, glossary=glossary)
            backend_translations[backend_name] = translated
        except (RuntimeError, Exception):
            backend_translations[backend_name] = [None] * len(texts)

    for i, text in enumerate(texts):
        translations = {
            name: trans[i] for name, trans in backend_translations.items()
        }
        results.append(ComparisonResult(original=text, translations=translations))

    return results


def format_comparison_table(results: list[ComparisonResult], max_width: int = 40) -> str:
    """Format comparison results as a readable table."""
    if not results:
        return "No results"

    backends = list(results[0].translations.keys())
    lines = []

    # Header
    header = f"{'Original':<{max_width}} | " + " | ".join(f"{b:<{max_width}}" for b in backends)
    lines.append(header)
    lines.append("-" * len(header))

    # Rows
    for r in results:
        orig = r.original[:max_width].ljust(max_width)
        cols = []
        for b in backends:
            t = r.translations.get(b) or "(failed)"
            cols.append(t[:max_width].ljust(max_width))
        lines.append(f"{orig} | " + " | ".join(cols))

    return "\n".join(lines)


def format_comparison_json(results: list[ComparisonResult]) -> str:
    """Format comparison results as JSON."""
    data = []
    for r in results:
        data.append({
            "original": r.original,
            "translations": r.translations,
        })
    return json.dumps(data, ensure_ascii=False, indent=2)
