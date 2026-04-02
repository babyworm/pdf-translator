# pdf_translator/core/pdf_builder.py
from __future__ import annotations

import io
import json
import logging
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from pdf_translator.core.chunker import is_math
from pdf_translator.core.extractor import Element

logger = logging.getLogger(__name__)

_JAVA_DIR = Path(__file__).resolve().parent.parent / "java"
_JAVA_CLASS = "PdfBuilder"


def _java_available() -> bool:
    """Check if Java + compiled PdfBuilder class are available."""
    if not shutil.which("java"):
        return False
    class_file = _JAVA_DIR / f"{_JAVA_CLASS}.class"
    if class_file.exists():
        return True
    # Try to compile
    return _ensure_compiled()


def _ensure_compiled() -> bool:
    """Compile PdfBuilder.java if .class is missing. Returns True on success."""
    java_src = _JAVA_DIR / f"{_JAVA_CLASS}.java"
    if not java_src.exists():
        return False
    jar = _find_opendataloader_jar()
    if not jar:
        return False
    javac = shutil.which("javac")
    if not javac:
        return False
    try:
        subprocess.run(
            [javac, "-cp", str(jar), "-d", str(_JAVA_DIR), str(java_src)],
            capture_output=True, timeout=30,
        )
        return (_JAVA_DIR / f"{_JAVA_CLASS}.class").exists()
    except (subprocess.TimeoutExpired, OSError):
        return False


def _find_opendataloader_jar() -> Path | None:
    """Locate the opendataloader-pdf JAR (contains PDFBox + Jackson)."""
    try:
        import opendataloader_pdf
        jar = Path(opendataloader_pdf.__file__).parent / "jar" / "opendataloader-pdf-cli.jar"
        if jar.exists():
            return jar
    except ImportError:
        pass
    return None


def _build_translations_json(
    elements: list[Element],
    translations: dict[int, str],
    json_path: str,
) -> None:
    """Build the translations JSON file for the Java PdfBuilder."""
    items = []
    for i, el in enumerate(elements):
        if not el.content.strip():
            continue
        if is_math(el.content):
            items.append({
                "page": el.page_number, "bbox": el.bbox,
                "text": el.content, "original": el.content,
                "font_size": el.font_size, "text_color": el.text_color,
                "type": el.type, "skip": True,
            })
        elif i in translations:
            items.append({
                "page": el.page_number, "bbox": el.bbox,
                "text": translations[i], "original": el.content,
                "font_size": el.font_size, "text_color": el.text_color,
                "type": el.type, "skip": False,
            })
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)


def _build_pdf_pdfbox(
    src_path: str,
    dst_path: str,
    elements: list[Element],
    translations: dict[int, str],
) -> bool:
    """Build PDF using the Java PDFBox backend. Returns True on success."""
    jar = _find_opendataloader_jar()
    if not jar:
        return False
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json_path = f.name
    try:
        _build_translations_json(elements, translations, json_path)
        cmd = [
            "java", "-cp", f"{jar}:{_JAVA_DIR}",
            _JAVA_CLASS, src_path, json_path, dst_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and "OK" in result.stdout:
            return True
        logger.warning("Java PdfBuilder failed: %s", result.stderr[-300:] if result.stderr else "")
        return False
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("Java PdfBuilder error: %s", e)
        return False
    finally:
        Path(json_path).unlink(missing_ok=True)


CJK_FONT_PATHS = [
    # Noto Sans CJK — preferred
    Path.home() / "Library/Fonts/NotoSansCJKkr-Regular.otf",  # macOS brew cask
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # Fallbacks
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
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
            return str(p)
    return None


def _is_vertical(bbox: list[float]) -> bool:
    """Detect if a bbox represents vertically-oriented text."""
    if len(bbox) != 4:
        return False
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return h > 0 and w > 0 and h / w > 3.0


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
    vertical: bool = False,
) -> None:
    """Draw *text* wrapped within the rectangle (x0, y0, x1, y1).

    Coordinates are in PDF-native space (origin bottom-left, y up).
    y1 > y0 (y1 is the top edge).
    If *vertical* is True, text is drawn rotated 90° counter-clockwise.
    """
    c.setFillColorRGB(*text_color)
    try:
        c.setFont(font_name, fontsize)
    except KeyError:
        c.setFont("Helvetica", fontsize)

    if vertical:
        # Rotate: use the height as the "writing width" and width as "writing height"
        box_width = y1 - y0  # long axis becomes writing direction
        box_height = x1 - x0
        line_height = fontsize * 1.2
        lines = _wrap_text(text, fontsize, box_width)

        c.saveState()
        # Translate to bottom-left of rect, then rotate 90° CCW
        c.translate(x0, y0)
        c.rotate(90)
        # After rotation: origin is at (x0, y0), x-axis points up, y-axis points left
        # Drawing space: (0, 0) to (box_width, -box_height)
        y_cursor = -fontsize
        for line in lines:
            if abs(y_cursor) > box_height:
                break
            c.drawString(0, y_cursor, line)
            y_cursor -= line_height
        c.restoreState()
    else:
        box_width = x1 - x0
        line_height = fontsize * 1.2
        lines = _wrap_text(text, fontsize, box_width)

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
    """Build a translated PDF.

    Tries Java PDFBox backend first (higher quality), falls back to
    pypdf+reportlab if Java is unavailable.
    """
    if _java_available():
        if _build_pdf_pdfbox(src_path, dst_path, elements, translations):
            return
        logger.warning("Java PDFBox failed, falling back to reportlab")
    _build_pdf_reportlab(src_path, dst_path, elements, translations, is_scanned)


def _build_pdf_reportlab(
    src_path: str,
    dst_path: str,
    elements: list[Element],
    translations: dict[int, str],
    is_scanned: bool = False,
) -> None:
    """Fallback: build PDF with pypdf+reportlab overlay approach.

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
            rect_width = x1 - x0
            rect_height = y_top - y_bottom

            # Skip tiny elements (page numbers, footnote markers)
            if rect_width < 10 and rect_height < 15:
                continue

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
            rect_width = x1 - x0
            rect_height = y_top - y_bottom

            # Skip tiny elements (page numbers, footnote markers)
            if rect_width < 10 and rect_height < 15:
                continue

            translated = translations[idx]
            vertical = _is_vertical(bbox)

            # For headings, preserve original font size (don't shrink)
            if el.type == "heading":
                fontsize = el.font_size
            elif vertical:
                fontsize = _fit_fontsize(translated, rect_height, rect_width, el.font_size)
            else:
                fontsize = _fit_fontsize(translated, rect_width, rect_height, el.font_size)

            # Never go below 6px
            fontsize = max(fontsize, 6.0)

            # Determine font
            font_name = "Helvetica"
            has_cjk = any(_is_cjk(ch) for ch in translated)
            if cjk_font_name and has_cjk:
                font_name = cjk_font_name
            # If no external CJK font registered, Helvetica is used as fallback.
            # reportlab doesn't have built-in CJK by font name like fitz did,
            # so we rely on the registered TTFont.

            # Determine text color
            # opendataloader-pdf returns colors as 0-1 floats (not 0-255 ints)
            # May be grayscale [0.5] or RGB [1.0, 0.0, 0.0]
            text_color = (0.0, 0.0, 0.0)
            if el.text_color:
                try:
                    vals = [float(v) for v in el.text_color]
                    # Detect 0-255 range and normalize
                    if any(v > 1.0 for v in vals):
                        vals = [v / 255.0 for v in vals]
                    if len(vals) == 1:
                        text_color = (vals[0], vals[0], vals[0])  # grayscale
                    elif len(vals) >= 3:
                        text_color = (vals[0], vals[1], vals[2])
                except (ValueError, TypeError):
                    pass

            try:
                _draw_text_in_rect(
                    c, translated, x0, y_bottom, x1, y_top,
                    fontsize, font_name, text_color, vertical=vertical,
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
