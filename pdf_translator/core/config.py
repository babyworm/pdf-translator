# pdf_translator/config.py
import os
from dataclasses import dataclass, field


def _default_workers() -> int:
    return min(os.cpu_count() or 4, 8)


@dataclass
class TranslatorConfig:
    input_path: str
    output_dir: str = "./output"
    workers: int = field(default_factory=_default_workers)
    source_lang: str = "auto"
    target_lang: str = "ko"
    effort: str = "low"
    pages: str | None = None
    use_cache: bool = True
    backend: str = "auto"
    glossary: str | None = None
    draft_only: bool = False
    build_from: str | None = None
    retranslate: str | None = None
    ocr_engine: str = "auto"
