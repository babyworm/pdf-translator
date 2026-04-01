from __future__ import annotations

import logging
import shutil

from pdf_translator.ocr.base import OCRResult

logger = logging.getLogger(__name__)

_LANG_MAP = {
    "en": "eng",
    "ko": "kor",
    "ja": "jpn",
    "zh": "chi_sim",
    "de": "deu",
    "fr": "fra",
    "es": "spa",
    "pt": "por",
    "it": "ita",
}


class TesseractOCREngine:
    name = "tesseract"

    def is_available(self) -> bool:
        return shutil.which("tesseract") is not None

    def extract(self, page_image: bytes, lang: str = "en") -> list[OCRResult]:
        try:
            import pytesseract
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(page_image))
            tess_lang = _LANG_MAP.get(lang, "eng")
            data = pytesseract.image_to_data(
                image, lang=tess_lang, output_type=pytesseract.Output.DICT
            )
            results = []
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                conf = int(data["conf"][i])
                if not text or conf < 30:
                    continue
                x, y, w, h = (
                    data["left"][i],
                    data["top"][i],
                    data["width"][i],
                    data["height"][i],
                )
                results.append(
                    OCRResult(
                        text=text,
                        bbox=[x, y, x + w, y + h],
                        confidence=conf / 100.0,
                    )
                )
            return results
        except Exception as e:
            logger.warning("Tesseract OCR failed: %s", e)
            return []
