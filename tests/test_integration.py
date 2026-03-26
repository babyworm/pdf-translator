"""End-to-end smoke test: extract → chunk → (mock) translate → pdf + md output."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import fitz

from pdf_translator.config import TranslatorConfig
from pdf_translator.cli import run


def _create_test_pdf(path: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Introduction", fontsize=18)
    page.insert_text((72, 140), "This is a test document.", fontsize=12)
    page.insert_text((72, 160), "It has multiple sentences.", fontsize=12)
    doc.save(path)
    doc.close()


def test_end_to_end_with_mock_codex():
    """Full pipeline with mocked extractor and codex to avoid external deps."""
    with tempfile.TemporaryDirectory() as d:
        pdf_path = str(Path(d) / "test.pdf")
        _create_test_pdf(pdf_path)

        cfg = TranslatorConfig(
            input_path=pdf_path,
            output_dir=str(Path(d) / "output"),
            workers=1,
            use_cache=False,
        )

        from pdf_translator.extractor import Element
        mock_elements = [
            Element(type="heading", content="Introduction", page_number=1,
                    bbox=[72, 90, 200, 110], font_size=18.0, level="h1"),
            Element(type="paragraph", content="This is a test document.", page_number=1,
                    bbox=[72, 130, 500, 150], font_size=12.0),
            Element(type="paragraph", content="It has multiple sentences.", page_number=1,
                    bbox=[72, 150, 500, 170], font_size=12.0),
        ]

        def mock_run_codex(prompt, effort, max_retries=2):
            import json
            try:
                start = prompt.index("[{")
                end = prompt.rindex("}]") + 2
                items = json.loads(prompt[start:end])
                result = [{"index": i, "text": f"[KO] {it['text']}"} for i, it in enumerate(items)]
                return json.dumps(result, ensure_ascii=False)
            except (ValueError, json.JSONDecodeError):
                return '[{"index": 0, "text": "[KO] translated"}]'

        class _InProcessPool:
            """Drop-in Pool replacement that runs map() in the current process."""
            def __init__(self, processes=1):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def map(self, fn, iterable):
                return [fn(item) for item in iterable]

        with patch("pdf_translator.cli.extract_pdf", return_value=mock_elements), \
             patch("pdf_translator.translator._run_codex", side_effect=mock_run_codex), \
             patch("pdf_translator.translator.Pool", _InProcessPool):
            run(cfg)

        out_dir = Path(d) / "output"
        assert (out_dir / "test_translated.pdf").exists()
        assert (out_dir / "test_translated.md").exists()

        md_content = (out_dir / "test_translated.md").read_text()
        assert "[KO]" in md_content
