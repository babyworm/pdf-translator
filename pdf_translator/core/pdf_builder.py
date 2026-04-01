# pdf_translator/core/pdf_builder.py
from __future__ import annotations

import logging
import math
from pathlib import Path

import fitz

from pdf_translator.core.extractor import Element

logger = logging.getLogger(__name__)

CJK_FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/baekmuk/batang.ttf",
    "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
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
    for ch in text:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7AF:
            return "korea"
        if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF:
            return "japan"
    return "china-ss"


def _sample_background_color(pixmap: fitz.Pixmap) -> tuple[float, float, float]:
    samples = pixmap.samples
    n = pixmap.n
    pixel_count = pixmap.width * pixmap.height
    if pixel_count == 0:
        return (1.0, 1.0, 1.0)
    # Sample every Nth pixel for performance (max 1000 samples)
    step = max(1, pixel_count // 1000)
    r_sum = g_sum = b_sum = 0
    sampled = 0
    if n < 3:
        for i in range(0, len(samples), n * step):
            r_sum += samples[i]
            sampled += 1
        gray = r_sum / (sampled * 255) if sampled else 1.0
        return (gray, gray, gray)
    for i in range(0, len(samples), n * step):
        if i + 2 < len(samples):
            r_sum += samples[i]
            g_sum += samples[i + 1]
            b_sum += samples[i + 2]
            sampled += 1
    if sampled == 0:
        return (1.0, 1.0, 1.0)
    return (r_sum / (sampled * 255), g_sum / (sampled * 255), b_sum / (sampled * 255))


def _fit_fontsize_v2(text: str, rect: fitz.Rect, max_size: float) -> float:
    lo, hi = 4.0, max_size
    for _ in range(12):
        mid = (lo + hi) / 2
        estimated_width = sum(mid * (1.0 if _is_cjk(ch) else 0.6) for ch in text)
        num_lines = math.ceil(estimated_width / rect.width) if rect.width > 0 else 1
        estimated_height = num_lines * mid * 1.2
        fits_width = estimated_width <= rect.width or num_lines > 1
        fits_height = estimated_height <= rect.height
        if fits_width and fits_height:
            lo = mid
        else:
            hi = mid
    return lo


def _build_html(text: str, fontsize: float, text_color: list[int], cjk_font: str | None) -> str:
    r = text_color[0] if text_color else 0
    g = text_color[1] if len(text_color) > 1 else 0
    b = text_color[2] if len(text_color) > 2 else 0
    font_family = "sans-serif"
    if cjk_font:
        font_family = f"CJK, {font_family}"
    elif any(_is_cjk(ch) for ch in text):
        font_family = f"{_builtin_cjk_fontname(text)}, {font_family}"
    return (
        f'<span style="font-size:{fontsize:.1f}px; '
        f'color:rgb({r},{g},{b}); '
        f'font-family:{font_family};">'
        f'{text}</span>'
    )


def build_pdf(
    src_path: str,
    dst_path: str,
    elements: list[Element],
    translations: dict[int, str],
    is_scanned: bool = False,
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
            page_height = page.rect.height

            if is_scanned:
                for idx, el in items:
                    bbox = el.bbox
                    if len(bbox) != 4:
                        continue
                    x0, y_bottom, x1, y_top = bbox
                    rect = fitz.Rect(x0, page_height - y_top, x1, page_height - y_bottom)
                    pixmap = page.get_pixmap(clip=rect)
                    bg_color = _sample_background_color(pixmap)
                    shape = page.new_shape()
                    shape.draw_rect(rect)
                    shape.finish(fill=bg_color)
                    shape.commit()
            else:
                for idx, el in items:
                    bbox = el.bbox
                    if len(bbox) != 4:
                        continue
                    x0, y_bottom, x1, y_top = bbox
                    rect = fitz.Rect(x0, page_height - y_top, x1, page_height - y_bottom)
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            for idx, el in items:
                bbox = el.bbox
                if len(bbox) != 4:
                    continue
                x0, y_bottom, x1, y_top = bbox
                rect = fitz.Rect(x0, page_height - y_top, x1, page_height - y_bottom)
                translated = translations[idx]
                fontsize = _fit_fontsize_v2(translated, rect, el.font_size)

                inserted = False
                try:
                    html = _build_html(translated, fontsize, el.text_color, cjk_font)
                    rc = page.insert_htmlbox(rect, html)
                    if rc >= 0:
                        inserted = True
                except Exception:
                    pass

                if not inserted:
                    try:
                        kwargs = {"fontsize": fontsize}
                        if cjk_font:
                            kwargs["fontfile"] = cjk_font
                            kwargs["fontname"] = "CJK"
                        elif any(_is_cjk(ch) for ch in translated):
                            kwargs["fontname"] = _builtin_cjk_fontname(translated)
                        color_floats = tuple(c / 255 for c in el.text_color[:3]) if el.text_color else (0, 0, 0)
                        kwargs["color"] = color_floats
                        rc = page.insert_textbox(rect, translated, **kwargs)
                        if rc >= 0:
                            inserted = True
                    except Exception:
                        pass

                if not inserted:
                    try:
                        page.insert_text(
                            rect.tl + fitz.Point(0, fontsize),
                            translated, fontsize=fontsize,
                        )
                    except Exception:
                        logger.warning("Failed to insert text at page %d, idx %d", page_num, idx)

        doc.save(dst_path)
    finally:
        doc.close()
