# tests/test_config.py
import os
from pdf_translator.config import TranslatorConfig


def test_default_config():
    cfg = TranslatorConfig(input_path="test.pdf")
    assert cfg.input_path == "test.pdf"
    assert cfg.output_dir == "./output"
    assert cfg.workers == min(os.cpu_count() or 4, 8)
    assert cfg.source_lang == "auto"
    assert cfg.target_lang == "ko"
    assert cfg.effort == "low"
    assert cfg.pages is None
    assert cfg.use_cache is True


def test_custom_config():
    cfg = TranslatorConfig(
        input_path="doc.pdf",
        output_dir="/tmp/out",
        workers=8,
        source_lang="ja",
        target_lang="en",
        effort="medium",
        pages="1-5",
        use_cache=False,
    )
    assert cfg.workers == 8
    assert cfg.pages == "1-5"
    assert cfg.use_cache is False
