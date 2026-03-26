from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from pdf_translator.extractor import Element

CJK_FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _find_cjk_font() -> str | None:
    for p in CJK_FONT_PATHS:
        if Path(p).exists():
            return p
    return None


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
            0xAC00 <= cp <= 0xD7AF or 0x3040 <= cp <= 0x30FF)


def _fit_fontsize(text: str, rect: fitz.Rect, max_size: float) -> float:
    lo, hi = 4.0, max_size
    for _ in range(10):
        mid = (lo + hi) / 2
        # CJK chars are roughly full-width (~1.0), Latin ~0.6
        estimated_width = sum(mid * (1.0 if _is_cjk(ch) else 0.6) for ch in text)
        if estimated_width <= rect.width:
            lo = mid
        else:
            hi = mid
    return lo


def build_pdf(
    src_path: str,
    dst_path: str,
    elements: list[Element],
    translations: dict[int, str],
) -> None:
    doc = fitz.open(src_path)

    cjk_font = _find_cjk_font()

    by_page: dict[int, list[tuple[int, Element]]] = {}
    for idx, el in enumerate(elements):
        if idx in translations:
            by_page.setdefault(el.page_number, []).append((idx, el))

    for page_num, items in by_page.items():
        if page_num < 1 or page_num > len(doc):
            continue
        page = doc[page_num - 1]

        for idx, el in items:
            bbox = el.bbox
            if len(bbox) != 4:
                continue

            page_height = page.rect.height
            x0, y_bottom, x1, y_top = bbox
            rect = fitz.Rect(x0, page_height - y_top, x1, page_height - y_bottom)

            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=None, fill=(1, 1, 1))
            shape.commit()

            translated = translations[idx]
            fontsize = _fit_fontsize(translated, rect, el.font_size)

            inserted = False
            # Try insert_textbox first (handles wrapping)
            try:
                kwargs = {"fontsize": fontsize}
                if cjk_font:
                    kwargs.update(fontfile=cjk_font, fontname="CJK")
                rc = page.insert_textbox(rect, translated, **kwargs)
                if rc >= 0:
                    inserted = True
            except Exception:
                pass

            # Fallback to insert_text if textbox failed
            if not inserted:
                try:
                    kwargs = {"fontsize": fontsize}
                    if cjk_font:
                        kwargs.update(fontfile=cjk_font, fontname="CJK")
                    page.insert_text(
                        rect.tl + fitz.Point(0, fontsize),
                        translated, **kwargs,
                    )
                except Exception:
                    page.insert_text(
                        rect.tl + fitz.Point(0, fontsize),
                        translated, fontsize=fontsize,
                    )

    doc.save(dst_path)
    doc.close()
