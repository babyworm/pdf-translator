from __future__ import annotations

import fitz


def is_scanned_page(page: fitz.Page, threshold: int = 50) -> bool:
    text = page.get_text("text").strip()
    return len(text) < threshold


def detect_pdf_type(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    try:
        if len(doc) == 0:
            return "scanned"
        scanned_count = 0
        sample_size = min(len(doc), 5)
        for i in range(sample_size):
            if is_scanned_page(doc[i]):
                scanned_count += 1
        return "scanned" if scanned_count > sample_size / 2 else "text"
    finally:
        doc.close()
