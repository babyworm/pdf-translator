from __future__ import annotations

from pypdf import PdfReader


def is_scanned_page(page, threshold: int = 50) -> bool:
    text = (page.extract_text() or "").strip()
    return len(text) < threshold


def detect_pdf_type(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    if len(reader.pages) == 0:
        return "scanned"
    scanned_count = 0
    sample_size = min(len(reader.pages), 5)
    for i in range(sample_size):
        if is_scanned_page(reader.pages[i]):
            scanned_count += 1
    return "scanned" if scanned_count > sample_size / 2 else "text"
