from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from pdf_translator.core.cache import TranslationCache
from pdf_translator.core.chunker import build_batches
from pdf_translator.core.config import TranslatorConfig
from pdf_translator.core.draft import Draft, DraftElement
from pdf_translator.core.extractor import extract_pdf
from pdf_translator.core.glossary import load_glossary
from pdf_translator.core.md_builder import build_markdown
from pdf_translator.core.pdf_builder import build_pdf
from pdf_translator.core.translator import detect_language, translate_all
from pdf_translator.core.translator.base import LANG_NAMES
from pdf_translator.core.translator.router import BackendRouter

console = Console()


def parse_args(argv: list[str] | None = None) -> TranslatorConfig:
    parser = argparse.ArgumentParser(
        prog="pdf-translator",
        description="Translate PDF documents with pluggable LLM backends",
    )
    parser.add_argument("input", nargs="?", default=None, help="Input PDF file path")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    default_workers = min(os.cpu_count() or 4, 8)
    parser.add_argument("--workers", type=int, default=default_workers, help="Parallel processes")
    parser.add_argument("--source-lang", default="auto", help="Source language (auto: detect)")
    parser.add_argument("--target-lang", default="ko", help="Target language code")
    parser.add_argument("--effort", default="low", help="Codex reasoning effort")
    parser.add_argument("--pages", default=None, help="Pages to process (e.g. 1,3,5-7)")
    parser.add_argument("--no-cache", action="store_true", help="Disable translation cache")
    parser.add_argument("--backend", default="auto",
                        help="Translation backend (auto, codex, claude-cli, gemini-cli, google-translate)")
    parser.add_argument("--glossary", default=None,
                        help="Glossary CSV path or built-in pack name (cs-general, ml-ai)")
    parser.add_argument("--draft-only", action="store_true",
                        help="Save draft JSON only, skip PDF build")
    parser.add_argument("--build-from", default=None,
                        help="Build PDF/MD from draft JSON")
    parser.add_argument("--retranslate", default=None,
                        help="Retranslate pending items in draft JSON")
    parser.add_argument("--ocr-engine", default="auto",
                        help="OCR engine (auto, surya, tesseract, none)")

    args = parser.parse_args(argv)
    return TranslatorConfig(
        input_path=args.input or "",
        output_dir=args.output_dir,
        workers=args.workers,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        effort=args.effort,
        pages=args.pages,
        use_cache=not args.no_cache,
        backend=args.backend,
        glossary=args.glossary,
        draft_only=args.draft_only,
        build_from=args.build_from,
        retranslate=args.retranslate,
        ocr_engine=args.ocr_engine,
    )


def _run_build_from(cfg: TranslatorConfig) -> None:
    """Mode A: Build PDF/MD from an existing draft JSON."""
    draft_path = Path(cfg.build_from)
    if not draft_path.exists():
        console.print(f"[red]Error: draft file {draft_path} not found[/red]")
        sys.exit(1)

    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    draft = Draft.load(str(draft_path))
    source_path = Path(draft.source_file)
    if not source_path.exists():
        console.print(f"[red]Error: source PDF {source_path} not found[/red]")
        sys.exit(1)

    stem = source_path.stem
    translations = draft.to_translations()
    elements = extract_pdf(str(source_path), output_dir=str(output_dir), pages=cfg.pages)

    console.print(f"  Draft: [cyan]{len(draft.elements)}[/cyan] elements, "
                  f"[cyan]{len(translations)}[/cyan] translated")

    pdf_out = str(output_dir / f"{stem}_translated.pdf")
    build_pdf(str(source_path), pdf_out, elements, translations)
    console.print(f"  PDF: [green]{pdf_out}[/green]")

    md_out = output_dir / f"{stem}_translated.md"
    md_content = build_markdown(elements, translations)
    md_out.write_text(md_content, encoding="utf-8")
    console.print(f"  Markdown: [green]{md_out}[/green]")
    console.print("[bold green]Done![/bold green]")


def _run_retranslate(cfg: TranslatorConfig) -> None:
    """Mode B: Retranslate pending items in a draft JSON."""
    draft_path = Path(cfg.retranslate)
    if not draft_path.exists():
        console.print(f"[red]Error: draft file {draft_path} not found[/red]")
        sys.exit(1)

    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    draft = Draft.load(str(draft_path))
    pending = draft.pending_indices()
    if not pending:
        console.print("  No pending items to retranslate.")
        console.print("[bold green]Done![/bold green]")
        return

    console.print(f"  Retranslating [cyan]{len(pending)}[/cyan] pending items...")

    pending_elements = [el for el in draft.elements if el.index in pending]
    from pdf_translator.core.extractor import Element
    fake_elements = [
        Element(type=el.type, content=el.original, page_number=el.page, bbox=el.bbox)
        for el in pending_elements
    ]
    batches = build_batches(fake_elements)

    source_lang = draft.source_lang
    target_lang = cfg.target_lang if cfg.target_lang != "ko" else draft.target_lang

    glossary_dict = None
    if cfg.glossary:
        glossary = load_glossary(cfg.glossary)
        if glossary:
            glossary_dict = glossary.to_prompt_dict()

    cache = TranslationCache(output_dir / "cache.db") if cfg.use_cache else None
    try:
        raw = translate_all(
            batches, source_lang=source_lang, target_lang=target_lang,
            effort=cfg.effort, workers=max(1, cfg.workers), cache=cache,
            backend=cfg.backend, glossary=glossary_dict,
        )
    finally:
        if cache:
            cache.flush()
            cache.close()

    # Map raw indices back to draft elements
    for raw_idx, translated_text in raw.items():
        if raw_idx < len(pending_elements):
            draft_el = pending_elements[raw_idx]
            draft_el.translated = translated_text
            draft_el.status = "accepted"

    draft.save(str(draft_path))
    console.print(f"  Updated draft: [green]{draft_path}[/green]")
    console.print("[bold green]Done![/bold green]")


def run(cfg: TranslatorConfig) -> None:
    # Mode A: build from draft
    if cfg.build_from:
        _run_build_from(cfg)
        return

    # Mode B: retranslate pending items in draft
    if cfg.retranslate:
        _run_retranslate(cfg)
        return

    # Mode C: default — extract, translate, build output
    input_path = Path(cfg.input_path)
    if not input_path.exists():
        console.print(f"[red]Error: {input_path} not found[/red]")
        sys.exit(1)

    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    with Progress(
        SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting PDF...", total=4)
        elements = extract_pdf(str(input_path), output_dir=str(output_dir), pages=cfg.pages)
        console.print(f"  Extracted [cyan]{len(elements)}[/cyan] text elements")

        if cfg.source_lang == "auto":
            cfg.source_lang = detect_language(elements)
            lang_label = LANG_NAMES.get(cfg.source_lang, cfg.source_lang)
            console.print(f"  Detected language: [cyan]{lang_label}[/cyan]")

        # Load glossary
        glossary_dict = None
        if cfg.glossary:
            glossary = load_glossary(cfg.glossary)
            if glossary:
                glossary_dict = glossary.to_prompt_dict()
                console.print(f"  Glossary: [cyan]{cfg.glossary}[/cyan] ({len(glossary_dict)} terms)")

        router = BackendRouter(effort=cfg.effort)
        backend_obj = router.select(cfg.backend)
        console.print(f"  Backend: [cyan]{backend_obj.name}[/cyan]")
        progress.update(task, advance=1)

        progress.update(task, description="Building batches...")
        valid_indices = [i for i, el in enumerate(elements) if el.content.strip()]
        batches = build_batches(elements)
        console.print(f"  Created [cyan]{len(batches)}[/cyan] translation batches")
        progress.update(task, advance=1)

        progress.update(task, description=f"Translating ({cfg.workers} workers)...")
        workers = max(1, cfg.workers)
        cache = TranslationCache(output_dir / "cache.db") if cfg.use_cache else None
        try:
            raw_translations = translate_all(
                batches,
                source_lang=cfg.source_lang,
                target_lang=cfg.target_lang,
                effort=cfg.effort,
                workers=workers,
                cache=cache,
                backend=cfg.backend,
                glossary=glossary_dict,
            )
            translations = {
                valid_indices[gi]: text
                for gi, text in raw_translations.items()
                if gi < len(valid_indices)
            }
            console.print(f"  Translated [cyan]{len(translations)}[/cyan] segments")
            progress.update(task, advance=1)

            # Draft-only mode: save draft and skip PDF/MD build
            if cfg.draft_only:
                draft_elements = [
                    DraftElement(
                        index=i, type=el.type, original=el.content,
                        translated=translations.get(i), page=el.page_number,
                        bbox=el.bbox,
                    )
                    for i, el in enumerate(elements) if el.content.strip()
                ]
                draft = Draft(
                    source_file=str(input_path), source_lang=cfg.source_lang,
                    target_lang=cfg.target_lang, backend=cfg.backend,
                    elements=draft_elements,
                )
                draft_path = output_dir / f"{stem}_draft.json"
                draft.save(str(draft_path))
                console.print(f"  Draft: [green]{draft_path}[/green]")
                progress.update(task, advance=1)
            else:
                progress.update(task, description="Generating output...")
                pdf_out = str(output_dir / f"{stem}_translated.pdf")
                build_pdf(str(input_path), pdf_out, elements, translations)
                console.print(f"  PDF: [green]{pdf_out}[/green]")

                md_out = output_dir / f"{stem}_translated.md"
                md_content = build_markdown(elements, translations)
                md_out.write_text(md_content, encoding="utf-8")
                console.print(f"  Markdown: [green]{md_out}[/green]")

                progress.update(task, advance=1)
        finally:
            if cache:
                cache.flush()
                cache.close()

    console.print("[bold green]Done![/bold green]")


def check_deps():
    """Check and report dependency status."""
    import os
    import shutil

    def _check(name, test_fn, hint=""):
        try:
            ok = test_fn()
        except Exception:
            ok = False
        mark = "✓" if ok else "✗"
        extra = f"  → {hint}" if not ok and hint else ""
        console.print(f"  {'[green]' if ok else '[red]'}{mark}[/] {name}{extra}")
        return ok

    console.print("[bold]PDF Translator — Dependency Check[/bold]\n")

    console.print("[bold]Core:[/bold]")
    _check("Python 3.10+", lambda: sys.version_info >= (3, 10))
    _check("Java", lambda: shutil.which("java") is not None, "brew install openjdk@21")
    _check("PyMuPDF", lambda: __import__("fitz") and True, "pip install PyMuPDF")
    _check("langdetect", lambda: __import__("langdetect") and True, "pip install langdetect")
    _check("deep_translator", lambda: __import__("deep_translator") and True, "pip install deep-translator")

    console.print("\n[bold]CLI Backends:[/bold]")
    _check("Codex CLI", lambda: shutil.which("codex") is not None, "npm install -g @openai/codex")
    _check("Claude CLI", lambda: shutil.which("claude") is not None, "npm install -g @anthropic-ai/claude-code")
    _check("Gemini CLI", lambda: shutil.which("gemini") is not None, "npm install -g @google/gemini-cli")

    console.print("\n[bold]API Keys:[/bold]")
    for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"]:
        _check(key, lambda k=key: bool(os.environ.get(k)), f"export {key}=...")

    console.print("\n[bold]OCR (optional):[/bold]")
    _check("Tesseract", lambda: shutil.which("tesseract") is not None, "brew install tesseract")
    _check("surya-ocr", lambda: __import__("surya") and True, "pip install surya-ocr")

    console.print("\n[bold]Web UI (optional):[/bold]")
    _check("FastAPI", lambda: __import__("fastapi") and True, "pip install pdf-translator[web]")
    _check("uvicorn", lambda: __import__("uvicorn") and True, "pip install pdf-translator[web]")


def run_compare(argv: list[str] | None = None):
    """Compare translation quality across backends."""
    import argparse
    parser = argparse.ArgumentParser(prog="pdf-translator compare")
    parser.add_argument("texts", nargs="+", help="Texts to compare")
    parser.add_argument("--source-lang", default="en")
    parser.add_argument("--target-lang", default="ko")
    parser.add_argument("--backends", default=None, help="Comma-separated backend names")
    parser.add_argument("--glossary", default=None, help="Glossary CSV or pack name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args(argv)

    from pdf_translator.core.compare import compare_backends, format_comparison_table, format_comparison_json

    backends = args.backends.split(",") if args.backends else None
    glossary_dict = None
    if args.glossary:
        from pdf_translator.core.glossary import load_glossary
        g = load_glossary(args.glossary)
        if g:
            glossary_dict = g.to_prompt_dict()

    console.print(f"[bold]Comparing backends for {len(args.texts)} text(s)...[/bold]\n")
    results = compare_backends(args.texts, args.source_lang, args.target_lang, backends, glossary_dict)

    if args.json:
        console.print(format_comparison_json(results))
    else:
        console.print(format_comparison_table(results))


def run_server(argv: list[str] | None = None):
    import argparse
    parser = argparse.ArgumentParser(prog="pdf-translator serve")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--data-dir", default="./pdf_translator_data")
    args = parser.parse_args(argv)

    try:
        import uvicorn

        from pdf_translator.web.app import create_app
        app = create_app(data_dir=args.data_dir)
        console.print("[bold green]Starting PDF Translator Web UI[/bold green]")
        console.print(f"  URL: [cyan]http://{args.host}:{args.port}[/cyan]")
        uvicorn.run(app, host=args.host, port=args.port)
    except ImportError:
        console.print("[red]Web UI requires additional dependencies. Install with:[/red]")
        console.print("  pip install pdf-translator[web]")
        sys.exit(1)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        run_server(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "compare":
        run_compare(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "check-deps":
        check_deps()
    else:
        cfg = parse_args()
        run(cfg)


if __name__ == "__main__":
    main()
