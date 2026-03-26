from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


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


def extract_pdf(pdf_path: str, output_dir: str | None = None, pages: str | None = None) -> list[Element]:
    import opendataloader_pdf

    if output_dir:
        # Use a fresh subdirectory to avoid stale JSON from previous runs
        work_dir = tempfile.mkdtemp(prefix="pdf_extract_", dir=output_dir)
    else:
        work_dir = tempfile.mkdtemp(prefix="pdf_translator_")
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

    return parse_elements(data)
