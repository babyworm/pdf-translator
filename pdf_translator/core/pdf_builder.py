from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from pdf_translator.core.extractor import Element

CJK_FONT_PATHS = [
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    # Noto CJK
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    # Ubuntu/Debian
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/baekmuk/batang.ttf",
    "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
    # Droid (wide CJK coverage)
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
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


def _builtin_cjk_fontname(text: str) -> str:
    """Pick a PyMuPDF built-in CJK font based on text content."""
    for ch in text:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7AF:
            return "korea"
        if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF:
            return "japan"
    return "china-ss"


def _cjk_font_kwargs(text: str, cjk_font_file: str | None) -> dict:
    """Build font kwargs — prefer external file, fallback to PyMuPDF built-in."""
    if cjk_font_file:
        return {"fontfile": cjk_font_file, "fontname": "CJK"}
    if any(_is_cjk(ch) for ch in text):
        return {"fontname": _builtin_cjk_fontname(text)}
    return {}


def _fit_fontsize(text: str, rect: fitz.Rect, max_size: float) -> float:
    import math
    lo, hi = 4.0, max_size
    for _ in range(10):
        mid = (lo + hi) / 2
        # CJK chars are roughly full-width (~1.0), Latin ~0.6
        estimated_width = sum(mid * (1.0 if _is_cjk(ch) else 0.6) for ch in text)
        num_lines = math.ceil(estimated_width / rect.width) if rect.width > 0 else 1
        estimated_height = num_lines * mid * 1.2  # 1.2 = line spacing factor
        fits_width = estimated_width <= rect.width or num_lines > 1
        fits_height = estimated_height <= rect.height
        if fits_width and fits_height:
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
    try:
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
                try:
                    kwargs = {"fontsize": fontsize}
                    kwargs.update(_cjk_font_kwargs(translated, cjk_font))
                    rc = page.insert_textbox(rect, translated, **kwargs)
                    if rc >= 0:
                        inserted = True
                except Exception:
                    pass

                if not inserted:
                    try:
                        kwargs = {"fontsize": fontsize}
                        kwargs.update(_cjk_font_kwargs(translated, cjk_font))
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
    finally:
        doc.close()
