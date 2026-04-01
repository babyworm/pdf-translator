from pdf_translator.ocr.base import OCREngine, OCRResult
from pdf_translator.ocr.detector import detect_pdf_type, is_scanned_page
from pdf_translator.ocr.surya_engine import SuryaOCREngine
from pdf_translator.ocr.tesseract_engine import TesseractOCREngine


def get_ocr_engine(name: str = "auto") -> OCREngine | None:
    if name == "surya":
        engine = SuryaOCREngine()
        return engine if engine.is_available() else None
    if name == "tesseract":
        engine = TesseractOCREngine()
        return engine if engine.is_available() else None
    if name == "auto":
        for EngineClass in [SuryaOCREngine, TesseractOCREngine]:
            engine = EngineClass()
            if engine.is_available():
                return engine
    return None
