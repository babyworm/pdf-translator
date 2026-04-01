from __future__ import annotations

import logging

from pdf_translator.ocr.base import OCRResult

logger = logging.getLogger(__name__)


class SuryaOCREngine:
    name = "surya"

    def __init__(self):
        self._det_model = None
        self._rec_model = None

    def _get_models(self):
        if self._det_model is None:
            from surya.model.detection.model import load_model as load_det_model
            from surya.model.recognition.model import load_model as load_rec_model
            self._det_model = load_det_model()
            self._rec_model = load_rec_model()
        return self._det_model, self._rec_model

    def is_available(self) -> bool:
        try:
            import surya  # noqa: F401

            return True
        except ImportError:
            return False

    def extract(self, page_image: bytes, lang: str = "en") -> list[OCRResult]:
        try:
            import io

            from PIL import Image
            from surya.ocr import run_ocr

            image = Image.open(io.BytesIO(page_image))
            det_model, rec_model = self._get_models()
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
