"""E2E test: real Google Translate API, mocked extractor (no Java needed)."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from pdf_translator.core import translate_pdf
from pdf_translator.core.extractor import Element
from pdf_translator.core.draft import Draft, DraftElement
from pdf_translator.core.glossary import load_builtin_pack
from pdf_translator.core.translator.backends.google_translate import GoogleTranslateBackend


def _create_test_pdf(path: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Introduction", fontsize=18)
    page.insert_text((72, 140), "The transformer model has revolutionized NLP.", fontsize=12)
    page.insert_text((72, 170), "We present results on standard benchmarks.", fontsize=12)
    doc.save(path)
    doc.close()


def _mock_elements() -> list[Element]:
    return [
        Element(type="heading", content="Introduction", page_number=1,
                bbox=[72, 82, 250, 105], font_size=18.0, text_color=[0, 0, 0], level="h1"),
        Element(type="paragraph", content="The transformer model has revolutionized NLP.",
                page_number=1, bbox=[72, 125, 500, 145], font_size=12.0, text_color=[0, 0, 0]),
        Element(type="paragraph", content="We present results on standard benchmarks.",
                page_number=1, bbox=[72, 155, 500, 175], font_size=12.0, text_color=[0, 0, 0]),
    ]


@pytest.fixture
def test_pdf(tmp_path):
    path = str(tmp_path / "test.pdf")
    _create_test_pdf(path)
    return path


class TestGoogleTranslateE2E:
    """Tests that use the real Google Translate API."""

    def test_backend_available(self):
        backend = GoogleTranslateBackend()
        assert backend.is_available() is True

    def test_single_text_translation(self):
        backend = GoogleTranslateBackend()
        result = backend.translate(["Hello world"], "en", "ko")
        assert result[0] is not None
        assert any(0xAC00 <= ord(c) <= 0xD7AF for c in result[0])

    def test_batch_translation(self):
        backend = GoogleTranslateBackend()
        texts = ["Good morning", "Thank you", "Machine learning"]
        results = backend.translate(texts, "en", "ko")
        assert len(results) == 3
        assert all(r is not None for r in results)

    def test_empty_text_passthrough(self):
        backend = GoogleTranslateBackend()
        results = backend.translate(["Hello", "", "World"], "en", "ko")
        assert results[1] == ""  # empty string passed through


class TestFullPipelineE2E:
    """Full pipeline tests with mocked extractor."""

    def test_translate_pdf_creates_outputs(self, test_pdf, tmp_path):
        with patch("pdf_translator.core.extract_pdf", return_value=_mock_elements()):
            result = translate_pdf(
                test_pdf, target_lang="ko", backend="google-translate",
                output_dir=str(tmp_path / "output"), use_cache=False,
            )

        assert Path(result["pdf_path"]).exists()
        assert Path(result["md_path"]).exists()
        assert result["segments_total"] == 3
        assert result["segments_translated"] >= 1

    def test_output_pdf_has_korean(self, test_pdf, tmp_path):
        with patch("pdf_translator.core.extract_pdf", return_value=_mock_elements()):
            result = translate_pdf(
                test_pdf, target_lang="ko", backend="google-translate",
                output_dir=str(tmp_path / "output"), use_cache=False,
            )

        doc = fitz.open(result["pdf_path"])
        text = doc[0].get_text()
        doc.close()
        assert any(0xAC00 <= ord(c) <= 0xD7AF for c in text)

    def test_output_markdown_has_korean(self, test_pdf, tmp_path):
        with patch("pdf_translator.core.extract_pdf", return_value=_mock_elements()):
            result = translate_pdf(
                test_pdf, target_lang="ko", backend="google-translate",
                output_dir=str(tmp_path / "output"), use_cache=False,
            )

        md = Path(result["md_path"]).read_text(encoding="utf-8")
        assert any(0xAC00 <= ord(c) <= 0xD7AF for c in md)
        assert "#" in md  # heading preserved

    def test_translate_with_glossary(self, test_pdf, tmp_path):
        glossary = {"transformer": "transformer", "NLP": "NLP"}
        with patch("pdf_translator.core.extract_pdf", return_value=_mock_elements()):
            result = translate_pdf(
                test_pdf, target_lang="ko", backend="google-translate",
                output_dir=str(tmp_path / "output"), use_cache=False,
                glossary=glossary,
            )

        md = Path(result["md_path"]).read_text(encoding="utf-8")
        assert result["segments_translated"] >= 1


class TestCacheE2E:
    """Test that caching works end-to-end."""

    def test_cache_speeds_up_second_run(self, test_pdf, tmp_path):
        out_dir = str(tmp_path / "output")
        with patch("pdf_translator.core.extract_pdf", return_value=_mock_elements()):
            # First run: no cache
            result1 = translate_pdf(
                test_pdf, target_lang="ko", backend="google-translate",
                output_dir=out_dir, use_cache=True,
            )
            # Second run: should use cache
            result2 = translate_pdf(
                test_pdf, target_lang="ko", backend="google-translate",
                output_dir=out_dir, use_cache=True,
            )

        assert result1["segments_translated"] == result2["segments_translated"]
        # Cache DB should exist
        assert (Path(out_dir) / "cache.db").exists()


class TestBuiltinGlossary:
    """Test built-in glossary packs load correctly."""

    def test_cs_general_has_entries(self):
        pack = load_builtin_pack("cs-general")
        assert pack is not None
        assert len(pack.entries) >= 20
        assert pack.get("API") == "API"

    def test_ml_ai_has_entries(self):
        pack = load_builtin_pack("ml-ai")
        assert pack is not None
        assert len(pack.entries) >= 20
        assert "BERT" in pack.keep_terms
