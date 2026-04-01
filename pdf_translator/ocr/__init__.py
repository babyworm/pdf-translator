from pdf_translator.ocr.base import OCREngine as OCREngine
from pdf_translator.ocr.base import OCRResult as OCRResult
from pdf_translator.ocr.detector import detect_pdf_type as detect_pdf_type
from pdf_translator.ocr.detector import is_scanned_page as is_scanned_page
from pdf_translator.ocr.surya_engine import SuryaOCREngine as SuryaOCREngine
from pdf_translator.ocr.tesseract_engine import TesseractOCREngine as TesseractOCREngine


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
