from __future__ import annotations

import logging

from pdf_translator.ocr.base import OCRResult

logger = logging.getLogger(__name__)


class SuryaOCREngine:
    name = "surya"

    def is_available(self) -> bool:
        try:
            import surya  # noqa: F401

            return True
        except ImportError:
            return False

    def extract(self, page_image: bytes, lang: str = "en") -> list[OCRResult]:
        try:
            from surya.ocr import run_ocr
            from surya.model.detection.model import load_model as load_det_model
            from surya.model.recognition.model import load_model as load_rec_model
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(page_image))
            det_model = load_det_model()
            rec_model = load_rec_model()
            ocr_results = run_ocr(
                [image], [det_model, rec_model], langs=[[lang]]
            )
            results = []
            if ocr_results and len(ocr_results) > 0:
                for line in ocr_results[0].text_lines:
                    results.append(
                        OCRResult(
                            text=line.text,
                            bbox=list(line.bbox),
                            confidence=line.confidence,
                        )
                    )
            return results
        except Exception as e:
            logger.warning("Surya OCR failed: %s", e)
            return []
