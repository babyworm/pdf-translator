# pdf_translator/core/pdf_builder.py
from __future__ import annotations

import io
import logging
import math
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

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

# Track whether the CJK font has already been registered with reportlab
_cjk_font_registered: str | None = None


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


def _register_cjk_font() -> str | None:
    """Try each CJK font path and register the first one that works.

    Returns the registered font name, or ``None`` if no font could be loaded.
    """
    global _cjk_font_registered  # noqa: PLW0603
    if _cjk_font_registered is not None:
        return _cjk_font_registered

    font_name = "CJK"
    for font_path in CJK_FONT_PATHS:
        if not Path(font_path).exists():
            continue
        try:
            if font_path.endswith(".ttc"):
                pdfmetrics.registerFont(
                    TTFont(font_name, font_path, subfontIndex=0),
                )
            else:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
            _cjk_font_registered = font_name
            logger.debug("Registered CJK font: %s", font_path)
            return font_name
        except Exception:
            logger.debug("Skipping incompatible font: %s", font_path)
            continue

    logger.warning("No compatible CJK font found")
    return None


def _fit_fontsize(text: str, width: float, height: float, max_size: float) -> float:
    """Binary-search for the largest font size that fits *text* in width x height."""
    lo, hi = 4.0, max_size
    for _ in range(12):
        mid = (lo + hi) / 2
        estimated_width = sum(mid * (1.0 if _is_cjk(ch) else 0.6) for ch in text)
        num_lines = math.ceil(estimated_width / width) if width > 0 else 1
        estimated_height = num_lines * mid * 1.2
        fits_width = estimated_width <= width or num_lines > 1
        fits_height = estimated_height <= height
        if fits_width and fits_height:
            lo = mid
        else:
            hi = mid
    return lo


def _wrap_text(text: str, fontsize: float, box_width: float) -> list[str]:
    """Wrap *text* into lines that fit within *box_width* at *fontsize*.

    Uses a simple character-width model: CJK chars are 1.0 * fontsize wide,
    Latin chars are 0.6 * fontsize wide.
    """
    if box_width <= 0:
        return [text]

    lines: list[str] = []
    current_line = ""
    current_width = 0.0

    for ch in text:
        if ch == "\n":
            lines.append(current_line)
            current_line = ""
            current_width = 0.0
            continue
        ch_width = fontsize * (1.0 if _is_cjk(ch) else 0.6)
        if current_width + ch_width > box_width and current_line:
            lines.append(current_line)
            current_line = ch
            current_width = ch_width
        else:
            current_line += ch
            current_width += ch_width

    if current_line:
        lines.append(current_line)
    return lines or [""]


def _draw_text_in_rect(
    c: canvas.Canvas,
    text: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    fontsize: float,
    font_name: str,
    text_color: tuple[float, float, float],
) -> None:
    """Draw *text* wrapped within the rectangle (x0, y0, x1, y1).

    Coordinates are in PDF-native space (origin bottom-left, y up).
    y1 > y0 (y1 is the top edge).
    """
    box_width = x1 - x0
    line_height = fontsize * 1.2
    lines = _wrap_text(text, fontsize, box_width)

    c.setFillColorRGB(*text_color)
    try:
        c.setFont(font_name, fontsize)
    except KeyError:
        c.setFont("Helvetica", fontsize)

    # Start drawing from top of box, descending
    y_cursor = y1 - fontsize  # baseline of first line
    for line in lines:
        if y_cursor < y0:
            break  # no more room
        c.drawString(x0, y_cursor, line)
        y_cursor -= line_height


def build_pdf(
    src_path: str,
    dst_path: str,
    elements: list[Element],
    translations: dict[int, str],
    is_scanned: bool = False,
) -> None:
    """Build a translated PDF by overlaying translated text onto the original.

    Strategy:
    1. Read the original PDF with pypdf.
    2. For each page that has translations, create a reportlab overlay:
       - Draw white (or background-color) rectangles to cover original text.
       - Draw translated text with proper font, size, color, and wrapping.
    3. Merge each overlay onto its corresponding original page.
    4. Write the result with pypdf.
    """
    writer = PdfWriter(clone_from=src_path)

    # Register CJK font if available
    cjk_font_name = _register_cjk_font()

    # Group translations by page number
    by_page: dict[int, list[tuple[int, Element]]] = {}
    for idx, el in enumerate(elements):
        if idx in translations:
            by_page.setdefault(el.page_number, []).append((idx, el))

    for page_idx in range(len(writer.pages)):
        page_num = page_idx + 1

        if page_num not in by_page:
            continue

        items = by_page[page_num]
        page = writer.pages[page_idx]

        # Determine page dimensions
        media_box = page.mediabox
        page_width = float(media_box.width)
        page_height = float(media_box.height)

        # Create an in-memory overlay PDF with reportlab
        overlay_buf = io.BytesIO()
        c = canvas.Canvas(overlay_buf, pagesize=(page_width, page_height))

        # --- Phase 1: Cover original text with filled rectangles ---
        for idx, el in items:
            bbox = el.bbox
            if len(bbox) != 4:
                continue
            x0, y_bottom, x1, y_top = bbox
            # bbox is already in PDF-native coordinates (origin bottom-left)
            rect_width = x1 - x0
            rect_height = y_top - y_bottom

            if is_scanned:
                # For scanned PDFs, use white background.
                # (The original fitz code sampled background color from the
                # pixmap, but white is a safe default for scanned documents.)
                c.setFillColorRGB(1.0, 1.0, 1.0)
            else:
                # For regular PDFs, white-out the original text area
                c.setFillColorRGB(1.0, 1.0, 1.0)

            c.rect(x0, y_bottom, rect_width, rect_height, stroke=0, fill=1)

        # --- Phase 2: Draw translated text ---
        for idx, el in items:
            bbox = el.bbox
            if len(bbox) != 4:
                continue
            x0, y_bottom, x1, y_top = bbox
            translated = translations[idx]

            rect_width = x1 - x0
            rect_height = y_top - y_bottom
            fontsize = _fit_fontsize(translated, rect_width, rect_height, el.font_size)

            # Determine font
            font_name = "Helvetica"
            has_cjk = any(_is_cjk(ch) for ch in translated)
            if cjk_font_name and has_cjk:
                font_name = cjk_font_name
            # If no external CJK font registered, Helvetica is used as fallback.
            # reportlab doesn't have built-in CJK by font name like fitz did,
            # so we rely on the registered TTFont.

            # Determine text color
            text_color = (0.0, 0.0, 0.0)
            if el.text_color and len(el.text_color) >= 3:
                text_color = (
                    el.text_color[0] / 255.0,
                    el.text_color[1] / 255.0,
                    el.text_color[2] / 255.0,
                )

            try:
                _draw_text_in_rect(
                    c, translated, x0, y_bottom, x1, y_top,
                    fontsize, font_name, text_color,
                )
            except Exception:
                logger.warning(
                    "Failed to insert text at page %d, idx %d", page_num, idx,
                )

        c.showPage()
        c.save()

        # Merge overlay onto the writer's page (already cloned)
        overlay_buf.seek(0)
        overlay_reader = PdfReader(overlay_buf)
        if overlay_reader.pages:
            page.merge_page(overlay_reader.pages[0])

    with open(dst_path, "wb") as f:
        writer.write(f)
