from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_java_checked = False


def _ensure_java(*, _force: bool = False) -> None:
    """Check that Java 11+ is available. Exit with install hints if missing."""
    global _java_checked
    if _java_checked and not _force:
        return
    _java_checked = True

    java_path = shutil.which("java")
    if java_path is None:
        os_name = platform.system()
        hints = {
            "Darwin": "  macOS:   brew install openjdk@21",
            "Linux": "  Ubuntu:  sudo apt install default-jdk\n  Fedora:  sudo dnf install java-21-openjdk",
        }
        hint = hints.get(os_name, "  Install Java 11+ for your platform")
        print(
            f"\nError: Java 11+ is required but not found.\n\n"
            f"Install Java:\n{hint}\n\n"
            f"Then run 'pdf-translator check-deps' to verify.\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Best-effort version check (warn only, don't block)
    try:
        result = subprocess.run(
            ["java", "-version"], capture_output=True, text=True, timeout=5
        )
        version_output = result.stderr or result.stdout
        match = re.search(r'"(\d+)', version_output)
        if match:
            major = int(match.group(1))
            if major < 11:
                print(
                    f"Warning: Java {major} detected. Java 11+ is recommended.",
                    file=sys.stderr,
                )
    except (subprocess.TimeoutExpired, OSError):
        pass  # If we can't check version, java binary exists — proceed


@dataclass
class Element:
    type: str
    content: str
    page_number: int
    bbox: list[float]
    font: str = ""
    font_size: float = 12.0
    text_color: list[int] = field(default_factory=lambda: [0, 0, 0])
    level: str | None = None


def parse_elements(data: dict) -> list[Element]:
    elements: list[Element] = []
    for kid in data.get("kids", []):
        _collect(kid, elements)
    return elements


def _collect(node: dict, out: list[Element]) -> None:
    content = node.get("content", "")
    node_type = node.get("type", "")

    if content and node_type in (
        "heading", "paragraph", "caption", "list item", "table cell",
    ):
        out.append(Element(
            type=node_type,
            content=content,
            page_number=node.get("page number", 0),
            bbox=node.get("bounding box", [0, 0, 0, 0]),
            font=node.get("font", ""),
            font_size=node.get("font size", 12.0),
            text_color=node.get("text color", [0, 0, 0]),
            level=node.get("level"),
        ))

    # Recurse into sub-elements; emit "table row end" after each row
    for child_key in ("kids", "list items"):
        for child in node.get(child_key, []):
            if isinstance(child, dict):
                _collect(child, out)

    # Handle table rows: collect cells, then emit row-end sentinel
    for row in node.get("rows", []):
        if isinstance(row, dict):
            for cell in row.get("cells", []):
                if isinstance(cell, dict):
                    _collect(cell, out)
            out.append(Element(
                type="table row end",
                content="",
                page_number=node.get("page number", 0),
                bbox=[0, 0, 0, 0],
            ))

    # Direct cells (outside rows context)
    if "cells" in node and "rows" not in node:
        for cell in node.get("cells", []):
            if isinstance(cell, dict):
                _collect(cell, out)


def extract_pdf(pdf_path: str, output_dir: str | None = None, pages: str | None = None, ocr_engine=None) -> list[Element]:
    _ensure_java()

    import opendataloader_pdf

    if output_dir:
        work_dir = tempfile.mkdtemp(prefix="pdf_extract_", dir=output_dir)
    else:
        work_dir = tempfile.mkdtemp(prefix="pdf_translator_")

    try:
        convert_args = dict(
            input_path=pdf_path,
            output_dir=work_dir,
            format="json",
        )
        if pages:
            convert_args["pages"] = pages

        opendataloader_pdf.convert(**convert_args)

        json_files = list(Path(work_dir).glob("*.json"))
        if not json_files:
            raise FileNotFoundError(f"No JSON output found in {work_dir}")

        with open(json_files[0], encoding="utf-8") as f:
            data = json.load(f)

        elements = parse_elements(data)

        # OCR fallback: if too few text elements found and OCR engine available
        if len(elements) < 3 and ocr_engine is not None:
            ocr_elements = _ocr_fallback(pdf_path, ocr_engine, pages)
            if len(ocr_elements) > len(elements):
                return ocr_elements

        return elements
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _ocr_fallback(pdf_path: str, ocr_engine, pages: str | None = None) -> list[Element]:
    """Extract text from PDF pages using OCR engine."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        elements: list[Element] = []
        page_count = len(pdf)
        page_range = _parse_pages(pages, page_count) if pages else range(page_count)

        for page_idx in page_range:
            if page_idx < 0 or page_idx >= page_count:
                continue
            page = pdf[page_idx]
            bitmap = page.render(scale=300 / 72)  # 300 DPI
            pil_image = bitmap.to_pil()
            import io
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            img_bytes = buf.getvalue()

            results = ocr_engine.extract(img_bytes, lang="en")

            for r in results:
                elements.append(Element(
                    type="paragraph",
                    content=r.text,
                    page_number=page_idx + 1,
                    bbox=r.bbox,
                    font_size=12.0,
                ))
        return elements
    finally:
        pdf.close()


def _parse_pages(pages_str: str, total: int) -> list[int]:
    """Parse page spec like '1,3,5-7' into 0-indexed list."""
    import logging
    logger = logging.getLogger(__name__)
    result: list[int] = []
    for part in pages_str.split(","):
        part = part.strip()
        try:
            if "-" in part:
                start, end = part.split("-", 1)
                for i in range(int(start) - 1, min(int(end), total)):
                    result.append(i)
            else:
                idx = int(part) - 1
                if 0 <= idx < total:
                    result.append(idx)
        except ValueError:
            logger.warning("Skipping invalid page spec: %s", part)
    return result
