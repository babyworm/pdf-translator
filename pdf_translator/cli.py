from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from pdf_translator.config import TranslatorConfig
from pdf_translator.extractor import extract_pdf
from pdf_translator.chunker import build_batches
from pdf_translator.cache import TranslationCache
from pdf_translator.translator import translate_all
from pdf_translator.pdf_builder import build_pdf
from pdf_translator.md_builder import build_markdown

console = Console()


def parse_args(argv: list[str] | None = None) -> TranslatorConfig:
    parser = argparse.ArgumentParser(
        prog="pdf-translator",
        description="Translate PDF documents using Codex CLI",
    )
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    parser.add_argument("--workers", type=int, default=4, help="Parallel processes")
    parser.add_argument("--source-lang", default="en", help="Source language code")
    parser.add_argument("--target-lang", default="ko", help="Target language code")
    parser.add_argument("--effort", default="low", help="Codex reasoning effort")
    parser.add_argument("--pages", default=None, help="Pages to process (e.g. 1,3,5-7)")
    parser.add_argument("--no-cache", action="store_true", help="Disable translation cache")

    args = parser.parse_args(argv)
    return TranslatorConfig(
        input_path=args.input,
        output_dir=args.output_dir,
        workers=args.workers,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        effort=args.effort,
        pages=args.pages,
        use_cache=not args.no_cache,
    )


def run(cfg: TranslatorConfig) -> None:
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
        progress.update(task, advance=1)

        progress.update(task, description="Building batches...")
        # Track original indices for elements that enter batches
        valid_indices = [i for i, el in enumerate(elements) if el.content.strip()]
        batches = build_batches(elements)
        console.print(f"  Created [cyan]{len(batches)}[/cyan] translation batches")
        progress.update(task, advance=1)

        progress.update(task, description=f"Translating ({cfg.workers} workers)...")
        workers = max(1, cfg.workers)
        cache = None
        try:
            if cfg.use_cache:
                cache = TranslationCache(output_dir / "cache.db")

            raw_translations = translate_all(
                batches,
                source_lang=cfg.source_lang,
                target_lang=cfg.target_lang,
                effort=cfg.effort,
                workers=workers,
                cache=cache,
            )
            # Remap batch-local indices to original element indices
            translations = {
                valid_indices[gi]: text
                for gi, text in raw_translations.items()
                if gi < len(valid_indices)
            }
            console.print(f"  Translated [cyan]{len(translations)}[/cyan] segments")
            progress.update(task, advance=1)

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
                cache.close()

    console.print("[bold green]Done![/bold green]")


def main():
    cfg = parse_args()
    run(cfg)


if __name__ == "__main__":
    main()
