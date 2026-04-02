import tempfile
from pathlib import Path

from reportlab.pdfgen import canvas

from pdf_translator.core.extractor import Element
from pdf_translator.core.qa import detect_pre_build_issues


def _el(content, type="paragraph", bbox=None, font_size=12.0):
    return Element(
        type=type, content=content, page_number=1,
        bbox=bbox or [72, 88, 500, 104], font_size=font_size,
    )


class TestPreBuildDetection:
    def test_no_issues_for_normal_translation(self):
        elements = [_el("Hello World")]
        translations = {0: "안녕 세계"}
        issues = detect_pre_build_issues(elements, translations)
        assert len(issues) == 0

    def test_detects_overflow_risk(self):
        el = _el("Hi", bbox=[0, 0, 50, 15])
        translations = {0: "이것은 매우 긴 번역 결과입니다 정말로 매우 긴 텍스트"}
        issues = detect_pre_build_issues([el], translations)
        assert len(issues) == 1
        assert "overflow" in issues[0]["issue"]

    def test_detects_empty_translation(self):
        elements = [_el("Hello World")]
        translations = {0: ""}
        issues = detect_pre_build_issues(elements, translations)
        assert len(issues) == 1
        assert "empty" in issues[0]["issue"]

    def test_detects_identical_translation(self):
        elements = [_el("Hello World")]
        translations = {0: "Hello World"}
        issues = detect_pre_build_issues(elements, translations)
        assert len(issues) == 1
        assert "identical" in issues[0]["issue"]

    def test_detects_heading_overflow(self):
        el = _el("Introduction", type="heading", bbox=[0, 0, 80, 16], font_size=12.0)
        translations = {0: "이것은 매우 긴 소제목 번역 결과입니다"}
        issues = detect_pre_build_issues([el], translations)
        assert len(issues) == 1
        assert "overflow" in issues[0]["issue"].lower() or "heading" in issues[0]["issue"].lower()

    def test_skips_untranslated_elements(self):
        elements = [_el("Hello"), _el("World")]
        translations = {0: "안녕"}  # index 1 not translated
        issues = detect_pre_build_issues(elements, translations)
        # Should not crash, only check translated elements
        assert all(i["index"] == 0 for i in issues) or len(issues) == 0


def _create_pdf_with_text(path, texts_by_page):
    """Create a test PDF with text on specified pages."""
    c = canvas.Canvas(str(path))
    for page_texts in texts_by_page:
        for i, text in enumerate(page_texts):
            c.drawString(72, 700 - i * 20, text)
        c.showPage()
    c.save()


class TestPostBuildDetection:
    def test_no_issues_when_text_present(self):
        from pdf_translator.core.qa import detect_post_build_issues
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.pdf"
            built = Path(d) / "built.pdf"
            _create_pdf_with_text(src, [["Hello World"]])
            _create_pdf_with_text(built, [["Translated World"]])

            elements = [_el("Hello World")]
            translations = {0: "Translated World"}
            issues = detect_post_build_issues(str(src), str(built), elements, translations)
            assert len(issues) == 0

    def test_detects_missing_text(self):
        from pdf_translator.core.qa import detect_post_build_issues
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.pdf"
            built = Path(d) / "built.pdf"
            _create_pdf_with_text(src, [["Hello", "World", "Test"]])
            _create_pdf_with_text(built, [["안녕"]])

            elements = [
                _el("Hello", bbox=[72, 88, 200, 104]),
                _el("World", bbox=[72, 60, 200, 76]),
                _el("Test", bbox=[72, 32, 200, 48]),
            ]
            translations = {0: "안녕", 1: "세계", 2: "테스트"}
            issues = detect_post_build_issues(str(src), str(built), elements, translations)
            assert len(issues) >= 1
            assert issues[0]["page"] == 1

    def test_detects_original_text_remaining(self):
        from pdf_translator.core.qa import detect_post_build_issues
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.pdf"
            built = Path(d) / "built.pdf"
            _create_pdf_with_text(src, [["Hello World"]])
            _create_pdf_with_text(built, [["Hello World", "안녕 세계"]])

            elements = [_el("Hello World")]
            translations = {0: "안녕 세계"}
            issues = detect_post_build_issues(str(src), str(built), elements, translations)
            assert len(issues) >= 1
