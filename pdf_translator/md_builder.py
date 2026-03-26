from __future__ import annotations

from pdf_translator.extractor import Element

HEADING_LEVELS = {
    "h1": "#", "h2": "##", "h3": "###",
    "h4": "####", "h5": "#####", "h6": "######",
    "Title": "#", "Subtitle": "##",
}


def _escape_cell(text: str) -> str:
    """Escape pipe characters and normalize newlines for GFM table cells."""
    return text.replace("|", "\\|").replace("\n", " ")


def _render_table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    rows = [[_escape_cell(cell) for cell in row] for row in rows]
    num_cols = max(len(r) for r in rows)
    widths = [0] * num_cols
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    widths = [max(w, 3) for w in widths]

    lines: list[str] = []
    for row_idx, row in enumerate(rows):
        padded = [cell.ljust(widths[i]) if i < len(row) else " " * widths[i]
                  for i, cell in enumerate(row + [""] * (num_cols - len(row)))]
        lines.append("| " + " | ".join(padded) + " |")
        if row_idx == 0:
            lines.append("| " + " | ".join("-" * w for w in widths) + " |")
    return lines


def build_markdown(elements: list[Element], translations: dict[int, str]) -> str:
    lines: list[str] = []
    current_page = 0

    table_buffer: list[list[str]] = []
    table_row: list[str] = []

    def flush_table():
        nonlocal table_buffer, table_row
        if table_row:
            table_buffer.append(table_row)
            table_row = []
        if table_buffer:
            lines.extend(_render_table(table_buffer))
            lines.append("")
            table_buffer = []

    for idx, el in enumerate(elements):
        if el.page_number != current_page:
            flush_table()
            if current_page > 0:
                lines.append("")
                lines.append("---")
                lines.append("")
            current_page = el.page_number

        text = translations.get(idx, el.content)

        if el.type == "heading":
            flush_table()
            prefix = HEADING_LEVELS.get(el.level or "h1", "#")
            lines.append(f"{prefix} {text}")
            lines.append("")
        elif el.type == "paragraph":
            flush_table()
            lines.append(text)
            lines.append("")
        elif el.type == "list item":
            flush_table()
            lines.append(f"- {text}")
        elif el.type == "caption":
            flush_table()
            lines.append(f"*{text}*")
            lines.append("")
        elif el.type == "table cell":
            table_row.append(text)
        elif el.type == "table row end":
            table_buffer.append(table_row)
            table_row = []
        else:
            flush_table()
            lines.append(text)
            lines.append("")

    flush_table()
    return "\n".join(lines)
