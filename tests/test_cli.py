"""Tests for CLI argument parsing and pipeline orchestration."""
import os
import sys
import pytest
from pdf_translator.cli.main import parse_args


def test_parse_args_minimal():
    cfg = parse_args(["input.pdf"])
    assert cfg.input_path == "input.pdf"
    assert cfg.output_dir == "./output"
    assert cfg.workers == min(os.cpu_count() or 4, 8)
    assert cfg.source_lang == "auto"
    assert cfg.target_lang == "ko"
    assert cfg.effort == "low"
    assert cfg.pages is None
    assert cfg.use_cache is True
    assert cfg.backend == "auto"


def test_parse_args_all_options():
    cfg = parse_args([
        "doc.pdf",
        "--output-dir", "/tmp/out",
        "--workers", "8",
        "--source-lang", "ja",
        "--target-lang", "en",
        "--effort", "medium",
        "--pages", "1-5,10",
        "--no-cache",
        "--backend", "codex",
    ])
    assert cfg.input_path == "doc.pdf"
    assert cfg.output_dir == "/tmp/out"
    assert cfg.workers == 8
    assert cfg.source_lang == "ja"
    assert cfg.target_lang == "en"
    assert cfg.effort == "medium"
    assert cfg.pages == "1-5,10"
    assert cfg.use_cache is False
    assert cfg.backend == "codex"


def test_parse_args_glossary():
    cfg = parse_args(["test.pdf", "--glossary", "ml-ai"])
    assert cfg.glossary == "ml-ai"


def test_parse_args_draft_only():
    cfg = parse_args(["test.pdf", "--draft-only"])
    assert cfg.draft_only is True


def test_parse_args_build_from():
    cfg = parse_args(["--build-from", "draft.json"])
    assert cfg.build_from == "draft.json"
    assert cfg.input_path == ""


def test_parse_args_retranslate():
    cfg = parse_args(["--retranslate", "draft.json"])
    assert cfg.retranslate == "draft.json"
    assert cfg.input_path == ""


def test_parse_args_ocr_engine():
    cfg = parse_args(["test.pdf", "--ocr-engine", "tesseract"])
    assert cfg.ocr_engine == "tesseract"


def test_parse_args_defaults_new_fields():
    cfg = parse_args(["test.pdf"])
    assert cfg.glossary is None
    assert cfg.draft_only is False
    assert cfg.build_from is None
    assert cfg.retranslate is None
    assert cfg.ocr_engine == "auto"
