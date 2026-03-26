"""Tests for CLI argument parsing and pipeline orchestration."""
import sys
import pytest
from pdf_translator.cli import parse_args


def test_parse_args_minimal():
    cfg = parse_args(["input.pdf"])
    assert cfg.input_path == "input.pdf"
    assert cfg.output_dir == "./output"
    assert cfg.workers == 4
    assert cfg.source_lang == "en"
    assert cfg.target_lang == "ko"
    assert cfg.effort == "low"
    assert cfg.pages is None
    assert cfg.use_cache is True


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
    ])
    assert cfg.input_path == "doc.pdf"
    assert cfg.output_dir == "/tmp/out"
    assert cfg.workers == 8
    assert cfg.source_lang == "ja"
    assert cfg.target_lang == "en"
    assert cfg.effort == "medium"
    assert cfg.pages == "1-5,10"
    assert cfg.use_cache is False


def test_parse_args_missing_input():
    with pytest.raises(SystemExit):
        parse_args([])
