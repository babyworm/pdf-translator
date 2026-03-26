# pdf_translator/config.py
from dataclasses import dataclass, field


@dataclass
class TranslatorConfig:
    input_path: str
    output_dir: str = "./output"
    workers: int = 4
    source_lang: str = "en"
    target_lang: str = "ko"
    effort: str = "low"
    pages: str | None = None
    use_cache: bool = True
