from __future__ import annotations

import argparse
import logging
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


def parse_args(argv: list[str] | None = None) -> tuple[TranslatorConfig, bool, str, str | None]:
    parser = argparse.ArgumentParser(
        prog="pdf-translator",
        description="Translate PDF documents with pluggable LLM backends",
        epilog="examples:\n"
               "  pdf-translator paper.pdf                          # translate to Korean (default)\n"
               "  pdf-translator paper.pdf --target-lang ja         # translate to Japanese\n"
               "  pdf-translator paper.pdf --backend claude-cli     # use Claude backend\n"
               "  pdf-translator paper.pdf --glossary cs-general    # with CS glossary\n"
               "  pdf-translator serve                              # start web UI\n"
               "  pdf-translator check-deps                         # check dependencies",
        formatter_class=type("_Fmt", (argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter), {}),
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
    parser.add_argument("--no-qa", action="store_true",
                        help="Disable QA review")
    parser.add_argument("--qa-retries", type=int, default=2,
                        help="Max QA retry attempts")
    parser.add_argument("--mode", default="md", choices=["md", "layout"],
                        help="Translation mode: md (markdown-based) or layout (PDF layout-preserving)")
    parser.add_argument("--hybrid", default=None, const="docling-fast", nargs="?",
                        help="Use hybrid AI backend for better reading order on complex layouts")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show detailed warnings and debug info")

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
        no_qa=args.no_qa,
        qa_retries=args.qa_retries,
    ), getattr(args, "verbose", False), getattr(args, "mode", "md"), getattr(args, "hybrid", None)


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
    lang = draft.target_lang or cfg.target_lang
    translations = draft.to_translations()
    elements = extract_pdf(str(source_path), output_dir=str(output_dir), pages=cfg.pages)

    console.print(f"  Draft: [cyan]{len(draft.elements)}[/cyan] elements, "
                  f"[cyan]{len(translations)}[/cyan] translated")

    pdf_out = str(output_dir / f"{stem}_{lang}.pdf")
    build_pdf(str(source_path), pdf_out, elements, translations)
    console.print(f"  PDF: [green]{pdf_out}[/green]")

    md_out = output_dir / f"{stem}_{lang}.md"
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


def run_md(cfg: TranslatorConfig, hybrid: str | None = None) -> None:
    """Markdown-based translation pipeline."""
    from pdf_translator.core.md_extractor import (
        clean_markdown,
        extract_markdown,
        split_paragraphs,
        truncate_at_references,
    )
    from pdf_translator.core.md_translator import translate_markdown

    input_path = Path(cfg.input_path)
    if not input_path.exists():
        console.print(f"[red]Error: {input_path} not found[/red]")
        sys.exit(1)

    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    console.print("[bold]Extracting markdown...[/bold]")
    raw_md = extract_markdown(str(input_path), pages=cfg.pages, hybrid=hybrid)
    cleaned = clean_markdown(raw_md)
    body = truncate_at_references(cleaned)
    paragraphs = split_paragraphs(body)
    console.print(f"  Extracted [cyan]{len(paragraphs)}[/cyan] paragraphs")

    # Save source markdown
    src_md_out = output_dir / f"{stem}_src.md"
    src_md_out.write_text(body, encoding="utf-8")
    console.print(f"  Source markdown: [green]{src_md_out}[/green]")

    if cfg.source_lang == "auto":
        from pdf_translator.core.extractor import Element
        from pdf_translator.core.translator import detect_language
        sample = [Element(type="paragraph", content=p, page_number=1, bbox=[0, 0, 0, 0])
                  for p in paragraphs[:5] if not p.startswith('#') and not p.startswith('!')]
        if sample:
            cfg.source_lang = detect_language(sample)
            from pdf_translator.core.translator.base import LANG_NAMES
            lang_label = LANG_NAMES.get(cfg.source_lang, cfg.source_lang)
            console.print(f"  Detected language: [cyan]{lang_label}[/cyan]")

    glossary_dict = None
    if cfg.glossary:
        glossary = load_glossary(cfg.glossary)
        if glossary:
            glossary_dict = glossary.to_prompt_dict()
            console.print(f"  Glossary: [cyan]{cfg.glossary}[/cyan] ({len(glossary_dict)} terms)")

    console.print("[bold]Translating...[/bold]")
    translated_md = translate_markdown(
        paragraphs,
        source_lang=cfg.source_lang,
        target_lang=cfg.target_lang,
        backend=cfg.backend,
        effort=cfg.effort,
        workers=cfg.workers,
        glossary=glossary_dict,
        use_cache=cfg.use_cache,
        output_dir=cfg.output_dir,
    )

    md_out = output_dir / f"{stem}_{cfg.target_lang}.md"
    md_out.write_text(translated_md, encoding="utf-8")
    console.print(f"  Markdown: [green]{md_out}[/green]")
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
                pdf_out = str(output_dir / f"{stem}_{cfg.target_lang}.pdf")

                if cfg.no_qa:
                    build_pdf(str(input_path), pdf_out, elements, translations)
                    console.print(f"  PDF: [green]{pdf_out}[/green]")
                else:
                    from pdf_translator.core.qa import (
                        collect_retranslate_indices,
                        detect_post_build_issues,
                        detect_pre_build_issues,
                        review_post_build,
                        review_pre_build,
                    )

                    qa_backend = None
                    if hasattr(backend_obj, "translate_raw"):
                        qa_backend = backend_obj

                    for retry in range(cfg.qa_retries + 1):
                        # Pre-build review
                        pre_results = []
                        pre_issues = detect_pre_build_issues(elements, translations)
                        if pre_issues and qa_backend:
                            console.print(f"  QA pre-build: [yellow]{len(pre_issues)} issues[/yellow]")
                            pre_results = review_pre_build(
                                pre_issues, qa_backend, cfg.source_lang, cfg.target_lang,
                            )
                            # Apply revisions
                            for item in pre_results:
                                if item.get("action") == "revise" and item.get("text"):
                                    translations[item["index"]] = item["text"]
                                elif item.get("action") == "skip" and item["index"] in translations:
                                    del translations[item["index"]]
                        elif pre_issues:
                            console.print(f"  QA pre-build: [yellow]{len(pre_issues)} issues (rule-based only)[/yellow]")

                        # Build PDF
                        build_pdf(str(input_path), pdf_out, elements, translations)

                        # Post-build QA (skip on last retry)
                        if retry == cfg.qa_retries:
                            break

                        post_issues = detect_post_build_issues(
                            str(input_path), pdf_out, elements, translations,
                        )
                        if not post_issues:
                            console.print("  QA post-build: [green]pass[/green]")
                            break

                        post_results = []
                        if qa_backend:
                            post_results = review_post_build(
                                post_issues, qa_backend, cfg.source_lang, cfg.target_lang,
                            )

                        failed = collect_retranslate_indices(pre_results, post_results)
                        if not failed:
                            console.print("  QA post-build: [green]pass (no retranslate needed)[/green]")
                            break

                        console.print(
                            f"  QA retry {retry + 1}/{cfg.qa_retries}: "
                            f"re-translating [yellow]{len(failed)}[/yellow] segments"
                        )

                        # Re-translate failed segments only
                        failed_elements = [
                            [el for i, el in enumerate(elements) if i in failed]
                        ]
                        if failed_elements[0]:
                            re_raw = translate_all(
                                failed_elements,
                                source_lang=cfg.source_lang,
                                target_lang=cfg.target_lang,
                                effort=cfg.effort,
                                workers=max(1, cfg.workers),
                                cache=None,
                                backend=cfg.backend,
                                glossary=glossary_dict,
                                layout_aware=True,
                            )
                            failed_list = sorted(failed)
                            for re_idx, text in re_raw.items():
                                if re_idx < len(failed_list) and text:
                                    translations[failed_list[re_idx]] = text

                    console.print(f"  PDF: [green]{pdf_out}[/green]")

                md_out = output_dir / f"{stem}_{cfg.target_lang}.md"
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
    _check("pypdf", lambda: __import__("pypdf") and True, "pip install pypdf")
    _check("reportlab", lambda: __import__("reportlab") and True, "pip install reportlab")
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

    from pdf_translator.core.compare import compare_backends, format_comparison_json, format_comparison_table

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
        cfg, verbose, mode, hybrid = parse_args()
        logging.basicConfig(
            level=logging.WARNING if verbose else logging.ERROR,
            format="%(name)s: %(message)s",
        )
        if not verbose:
            # Suppress Java library warnings (PDFBox, verapdf, etc.)
            log_props = str(Path(__file__).resolve().parent.parent / "java" / "logging.properties")
            os.environ["JAVA_TOOL_OPTIONS"] = f"-Djava.util.logging.config.file={log_props}"
        if not cfg.input_path and not cfg.build_from and not cfg.retranslate:
            parse_args(["--help"])
        if mode == "md" and not cfg.build_from and not cfg.retranslate:
            run_md(cfg, hybrid=hybrid)
        else:
            run(cfg)


if __name__ == "__main__":
    main()
