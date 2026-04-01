from pdf_translator.core.extractor import Element
from pdf_translator.core.md_builder import build_markdown


def _el(type: str, content: str, level: str | None = None, page: int = 1) -> Element:
    return Element(
        type=type, content=content, page_number=page,
        bbox=[0, 0, 100, 20], level=level,
    )


def test_heading():
    elements = [_el("heading", "Title", level="h1")]
    translations = {0: "제목"}
    md = build_markdown(elements, translations)
    assert md.strip() == "# 제목"


def test_paragraph():
    elements = [_el("paragraph", "Hello world")]
    translations = {0: "안녕 세계"}
    md = build_markdown(elements, translations)
    assert "안녕 세계" in md


def test_mixed_content():
    elements = [
        _el("heading", "Intro", level="h2"),
        _el("paragraph", "Some text"),
        _el("paragraph", "More text"),
    ]
    translations = {0: "소개", 1: "약간의 텍스트", 2: "더 많은 텍스트"}
    md = build_markdown(elements, translations)
    assert "## 소개" in md
    assert "약간의 텍스트" in md
    assert "더 많은 텍스트" in md


def test_page_separator():
    elements = [
        _el("paragraph", "Page 1 text", page=1),
        _el("paragraph", "Page 2 text", page=2),
    ]
    translations = {0: "1페이지", 1: "2페이지"}
    md = build_markdown(elements, translations)
    assert "---" in md


def test_untranslated_fallback():
    elements = [_el("paragraph", "Original")]
    translations = {}
    md = build_markdown(elements, translations)
    assert "Original" in md


def test_table_rendering():
    elements = [
        _el("table cell", "Name"),
        _el("table cell", "Age"),
        _el("table row end", ""),
        _el("table cell", "Alice"),
        _el("table cell", "30"),
        _el("table row end", ""),
    ]
    translations = {0: "이름", 1: "나이", 3: "앨리스", 4: "30"}
    md = build_markdown(elements, translations)
    assert "| 이름" in md
    assert "| 나이" in md
    assert "| 앨리스" in md
    assert "---" in md
