# PDF Translator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PDF에서 텍스트를 추출하고 Codex CLI로 병렬 번역하여 레이아웃 보존 PDF + Markdown을 생성하는 CLI 도구

**Architecture:** opendataloader-pdf로 JSON 추출(bounding box 포함) → 배치 청킹 → multiprocessing Pool로 codex exec 병렬 호출 → PyMuPDF로 원본 PDF 위에 번역 오버레이 + 구조 기반 Markdown 생성

**Tech Stack:** Python 3.10+, opendataloader-pdf, PyMuPDF (fitz), SQLite3, Codex CLI, rich

---

## File Structure

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | 프로젝트 메타데이터, 의존성, entry point |
| `pdf_translator/__init__.py` | 패키지 초기화 |
| `pdf_translator/config.py` | `TranslatorConfig` dataclass — 모든 설정을 한 곳에 |
| `pdf_translator/extractor.py` | opendataloader-pdf 래퍼, JSON 파싱하여 `Element` 리스트 반환 |
| `pdf_translator/chunker.py` | Element 리스트 → 번역 배치 분리 |
| `pdf_translator/cache.py` | SQLite 기반 번역 캐시 (SHA-256 키) |
| `pdf_translator/translator.py` | codex exec 호출 + multiprocessing Pool 병렬 처리 |
| `pdf_translator/pdf_builder.py` | PyMuPDF로 원본 PDF에 번역 오버레이 |
| `pdf_translator/md_builder.py` | 구조 기반 Markdown 생성 |
| `pdf_translator/cli.py` | argparse CLI 진입점 + 파이프라인 오케스트레이션 |
| `tests/test_config.py` | config 테스트 |
| `tests/test_chunker.py` | chunker 테스트 |
| `tests/test_cache.py` | cache 테스트 |
| `tests/test_translator.py` | translator 테스트 (codex mock) |
| `tests/test_md_builder.py` | markdown builder 테스트 |
| `tests/test_extractor.py` | extractor 테스트 |
| `tests/test_pdf_builder.py` | pdf builder 테스트 |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `pdf_translator/__init__.py`
- Create: `pdf_translator/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "pdf-translator"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "opendataloader-pdf>=0.3",
    "PyMuPDF>=1.24",
    "rich>=13.0",
]

[project.scripts]
pdf-translator = "pdf_translator.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `pdf_translator/__init__.py`**

```python
"""PDF Translator — extract, translate, rebuild."""
```

- [ ] **Step 3: Write failing test for config**

```python
# tests/test_config.py
from pdf_translator.config import TranslatorConfig


def test_default_config():
    cfg = TranslatorConfig(input_path="test.pdf")
    assert cfg.input_path == "test.pdf"
    assert cfg.output_dir == "./output"
    assert cfg.workers == 4
    assert cfg.source_lang == "en"
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /Users/babyworm/work/pdf_translator && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 5: Implement config**

```python
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Install dependencies**

Run: `cd /Users/babyworm/work/pdf_translator && pip install -e ".[dev]" 2>/dev/null; pip install opendataloader-pdf PyMuPDF rich pytest`

- [ ] **Step 8: Commit**

```bash
git init
git add pyproject.toml pdf_translator/__init__.py pdf_translator/config.py tests/test_config.py
git commit -m "feat: project scaffolding with TranslatorConfig"
```

---

### Task 2: Extractor — opendataloader-pdf Wrapper

**Files:**
- Create: `pdf_translator/extractor.py`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Define Element dataclass and write test**

```python
# tests/test_extractor.py
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from pdf_translator.extractor import Element, parse_elements, extract_pdf


def test_element_creation():
    el = Element(
        type="paragraph",
        content="Hello world",
        page_number=1,
        bbox=[72.0, 700.0, 540.0, 730.0],
        font="Arial",
        font_size=12.0,
        text_color=[0, 0, 0],
        level=None,
    )
    assert el.content == "Hello world"
    assert el.bbox == [72.0, 700.0, 540.0, 730.0]


def test_parse_elements_from_json():
    """Parse opendataloader JSON output into Element list."""
    raw = {
        "file name": "test.pdf",
        "number of pages": 1,
        "kids": [
            {
                "type": "heading",
                "content": "Title",
                "page number": 1,
                "bounding box": [72.0, 700.0, 540.0, 730.0],
                "font": "Arial",
                "font size": 24,
                "text color": [0, 0, 0],
                "level": "h1",
            },
            {
                "type": "paragraph",
                "content": "Body text here.",
                "page number": 1,
                "bounding box": [72.0, 650.0, 540.0, 690.0],
                "font": "Times",
                "font size": 12,
                "text color": [0, 0, 0],
            },
        ],
    }
    elements = parse_elements(raw)
    assert len(elements) == 2
    assert elements[0].type == "heading"
    assert elements[0].level == "h1"
    assert elements[1].content == "Body text here."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_extractor.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement Element and parse_elements**

```python
# pdf_translator/extractor.py
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Element:
    type: str
    content: str
    page_number: int
    bbox: list[float]
    font: str = ""
    font_size: float = 12.0
    text_color: list[int] = field(default_factory=lambda: [0, 0, 0])
    level: str | None = None


def parse_elements(data: dict) -> list[Element]:
    """Parse opendataloader JSON into a flat list of Elements."""
    elements: list[Element] = []
    for kid in data.get("kids", []):
        _collect(kid, elements)
    return elements


def _collect(node: dict, out: list[Element]) -> None:
    """Recursively collect text elements from a node tree."""
    content = node.get("content", "")
    node_type = node.get("type", "")

    if content and node_type in (
        "heading", "paragraph", "caption", "list item", "table cell",
    ):
        out.append(Element(
            type=node_type,
            content=content,
            page_number=node.get("page number", 0),
            bbox=node.get("bounding box", [0, 0, 0, 0]),
            font=node.get("font", ""),
            font_size=node.get("font size", 12.0),
            text_color=node.get("text color", [0, 0, 0]),
            level=node.get("level"),
        ))

    # Recurse into sub-elements (tables, lists, etc.)
    for child_key in ("kids", "rows", "list items", "cells"):
        for child in node.get(child_key, []):
            if isinstance(child, dict):
                _collect(child, out)


def extract_pdf(pdf_path: str, output_dir: str | None = None, pages: str | None = None) -> list[Element]:
    """Extract structured elements from a PDF using opendataloader-pdf."""
    import opendataloader_pdf

    work_dir = output_dir or tempfile.mkdtemp(prefix="pdf_translator_")
    convert_args = dict(
        input_path=pdf_path,
        output_dir=work_dir,
        format="json",
    )
    if pages:
        convert_args["pages"] = pages

    opendataloader_pdf.convert(**convert_args)

    # Find the generated JSON file
    json_files = list(Path(work_dir).glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON output found in {work_dir}")

    with open(json_files[0], encoding="utf-8") as f:
        data = json.load(f)

    return parse_elements(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/extractor.py tests/test_extractor.py
git commit -m "feat: PDF extractor with opendataloader-pdf wrapper"
```

---

### Task 3: Chunker — Batch Builder

**Files:**
- Create: `pdf_translator/chunker.py`
- Create: `tests/test_chunker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_chunker.py
from pdf_translator.extractor import Element
from pdf_translator.chunker import build_batches

def _el(content: str, page: int = 1) -> Element:
    return Element(
        type="paragraph", content=content, page_number=page,
        bbox=[0, 0, 100, 20],
    )

def test_single_batch():
    elements = [_el("Hello"), _el("World")]
    batches = build_batches(elements)
    assert len(batches) == 1
    assert len(batches[0]) == 2


def test_split_by_count():
    elements = [_el(f"item {i}") for i in range(50)]
    batches = build_batches(elements, max_segments=40)
    assert len(batches) == 2
    assert len(batches[0]) == 40
    assert len(batches[1]) == 10


def test_split_by_chars():
    elements = [_el("a" * 2000) for _ in range(5)]
    batches = build_batches(elements, max_chars=4500)
    # Each item is 2000 chars, so max 2 per batch
    assert len(batches) >= 3


def test_empty_input():
    assert build_batches([]) == []


def test_skips_empty_content():
    elements = [_el(""), _el("real text"), _el("   ")]
    batches = build_batches(elements)
    assert len(batches) == 1
    assert len(batches[0]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_chunker.py -v`
Expected: FAIL

- [ ] **Step 3: Implement chunker**

```python
# pdf_translator/chunker.py
from __future__ import annotations

from pdf_translator.extractor import Element


def build_batches(
    elements: list[Element],
    max_segments: int = 40,
    max_chars: int = 4500,
) -> list[list[Element]]:
    """Split elements into translation batches respecting dual constraints."""
    # Filter out elements with empty/whitespace-only content
    valid = [e for e in elements if e.content.strip()]
    if not valid:
        return []

    batches: list[list[Element]] = []
    current: list[Element] = []
    current_chars = 0

    for el in valid:
        el_chars = len(el.content)
        would_exceed_segments = len(current) >= max_segments
        would_exceed_chars = current_chars + el_chars > max_chars and current

        if would_exceed_segments or would_exceed_chars:
            batches.append(current)
            current = []
            current_chars = 0

        current.append(el)
        current_chars += el_chars

    if current:
        batches.append(current)

    return batches
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_chunker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/chunker.py tests/test_chunker.py
git commit -m "feat: dual-constraint batch chunker"
```

---

### Task 4: Translation Cache

**Files:**
- Create: `pdf_translator/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cache.py
import tempfile
from pathlib import Path
from pdf_translator.cache import TranslationCache


def test_cache_miss():
    with tempfile.TemporaryDirectory() as d:
        cache = TranslationCache(Path(d) / "cache.db")
        result = cache.get("hello", "en", "ko")
        assert result is None


def test_cache_put_and_get():
    with tempfile.TemporaryDirectory() as d:
        cache = TranslationCache(Path(d) / "cache.db")
        cache.put("hello", "en", "ko", "안녕하세요")
        assert cache.get("hello", "en", "ko") == "안녕하세요"


def test_cache_different_langs():
    with tempfile.TemporaryDirectory() as d:
        cache = TranslationCache(Path(d) / "cache.db")
        cache.put("hello", "en", "ko", "안녕하세요")
        cache.put("hello", "en", "ja", "こんにちは")
        assert cache.get("hello", "en", "ko") == "안녕하세요"
        assert cache.get("hello", "en", "ja") == "こんにちは"


def test_cache_persistence():
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "cache.db"
        cache1 = TranslationCache(db_path)
        cache1.put("test", "en", "ko", "테스트")
        cache1.close()

        cache2 = TranslationCache(db_path)
        assert cache2.get("test", "en", "ko") == "테스트"
        cache2.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cache.py -v`
Expected: FAIL

- [ ] **Step 3: Implement cache**

```python
# pdf_translator/cache.py
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


class TranslationCache:
    def __init__(self, db_path: Path | str):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS translations (
                source_hash TEXT NOT NULL,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                translated TEXT NOT NULL,
                PRIMARY KEY (source_hash, source_lang, target_lang)
            )"""
        )
        self._conn.commit()

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def get(self, source: str, source_lang: str, target_lang: str) -> str | None:
        row = self._conn.execute(
            "SELECT translated FROM translations WHERE source_hash=? AND source_lang=? AND target_lang=?",
            (self._hash(source), source_lang, target_lang),
        ).fetchone()
        return row[0] if row else None

    def put(self, source: str, source_lang: str, target_lang: str, translated: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO translations (source_hash, source_lang, target_lang, translated) VALUES (?, ?, ?, ?)",
            (self._hash(source), source_lang, target_lang, translated),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/cache.py tests/test_cache.py
git commit -m "feat: SQLite translation cache with SHA-256 keying"
```

---

### Task 5: Translator — Codex CLI Parallel Execution

**Files:**
- Create: `pdf_translator/translator.py`
- Create: `tests/test_translator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_translator.py
import json
from unittest.mock import patch, MagicMock
from pdf_translator.extractor import Element
from pdf_translator.translator import (
    build_prompt,
    parse_codex_response,
    translate_batch,
    translate_all,
)


def _el(content: str) -> Element:
    return Element(
        type="paragraph", content=content, page_number=1,
        bbox=[0, 0, 100, 20],
    )


def test_build_prompt():
    batch = [_el("Hello"), _el("World")]
    prompt = build_prompt(batch, "en", "ko")
    assert "Hello" in prompt
    assert "Korean" in prompt or "ko" in prompt


def test_parse_codex_response_json():
    response = json.dumps([
        {"index": 0, "text": "안녕하세요"},
        {"index": 1, "text": "세계"},
    ])
    results = parse_codex_response(response, count=2)
    assert results == ["안녕하세요", "세계"]


def test_parse_codex_response_fallback():
    """Non-JSON response: split by lines."""
    response = "안녕하세요\n세계"
    results = parse_codex_response(response, count=2)
    assert results == ["안녕하세요", "세계"]


def test_translate_batch_calls_codex():
    batch = [_el("Hello")]
    mock_result = json.dumps([{"index": 0, "text": "안녕하세요"}])

    with patch("pdf_translator.translator._run_codex", return_value=mock_result):
        results = translate_batch(batch, "en", "ko", effort="low")
        assert results == ["안녕하세요"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_translator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement translator**

```python
# pdf_translator/translator.py
from __future__ import annotations

import json
import subprocess
import time
from multiprocessing import Pool
from functools import partial

from pdf_translator.extractor import Element


LANG_NAMES = {
    "en": "English", "ko": "Korean", "ja": "Japanese",
    "zh": "Chinese", "de": "German", "fr": "French",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian",
}


def build_prompt(batch: list[Element], source_lang: str, target_lang: str) -> str:
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)
    items = [{"index": i, "text": el.content} for i, el in enumerate(batch)]

    return f"""You are a professional translator.
Translate the following text from {src_name} to {tgt_name}.
Preserve the original structure and formatting.
Input is a JSON array of indexed items.
Output ONLY a JSON array in the same order with translated text.
Do not merge or split items. Keep untranslatable terms as-is.

Input:
{json.dumps(items, ensure_ascii=False)}"""


def parse_codex_response(response: str, count: int) -> list[str]:
    """Parse codex output, trying JSON first, then line-based fallback."""
    response = response.strip()

    # Try JSON array parse
    try:
        # Handle markdown code block wrapping
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(
                l for l in lines if not l.startswith("```")
            )

        data = json.loads(response)
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                sorted_items = sorted(data, key=lambda x: x.get("index", 0))
                return [item.get("text", "") for item in sorted_items]
            return [str(item) for item in data]
    except (json.JSONDecodeError, KeyError):
        pass

    # Fallback: split by lines
    lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
    if len(lines) >= count:
        return lines[:count]

    # Last resort: return whatever we got, padded
    return lines + [""] * (count - len(lines))


def _run_codex(prompt: str, effort: str, max_retries: int = 2) -> str:
    """Execute codex CLI and return stdout."""
    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(
                ["codex", "exec", "-s", "read-only", "--effort", effort, prompt],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            if attempt < max_retries:
                time.sleep(min(0.5 * (2 ** attempt), 4.0))
        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                time.sleep(min(0.5 * (2 ** attempt), 4.0))

    return ""


def translate_batch(
    batch: list[Element],
    source_lang: str,
    target_lang: str,
    effort: str = "low",
) -> list[str]:
    """Translate a single batch of elements via codex."""
    prompt = build_prompt(batch, source_lang, target_lang)
    response = _run_codex(prompt, effort)
    if not response:
        return [el.content for el in batch]  # fallback: original text
    return parse_codex_response(response, count=len(batch))


def _worker_translate(
    work_item: tuple[list[dict], str, str, str],
) -> list[tuple[int, str, str]]:
    """Worker function for multiprocessing.

    Args:
        work_item: (items, source_lang, target_lang, effort)
            items: list of dicts with keys type, content, page_number, bbox, global_idx

    Returns:
        list of (global_idx, translated_text, original_content) tuples
    """
    items, source_lang, target_lang, effort = work_item
    elements = [
        Element(
            type=d["type"], content=d["content"], page_number=d["page_number"],
            bbox=d["bbox"],
        )
        for d in items
    ]
    translations = translate_batch(elements, source_lang, target_lang, effort)
    return [
        (item["global_idx"], translated, item["content"])
        for item, translated in zip(items, translations)
    ]


def translate_all(
    batches: list[list[Element]],
    source_lang: str,
    target_lang: str,
    effort: str = "low",
    workers: int = 4,
    cache=None,
) -> dict[int, str]:
    """Translate all batches in parallel. Returns {element_global_index: translated_text}."""
    results: dict[int, str] = {}
    work_items: list[tuple[list[dict], str, str, str]] = []
    global_idx = 0

    for batch in batches:
        batch_items: list[dict] = []
        for el in batch:
            if cache:
                cached = cache.get(el.content, source_lang, target_lang)
                if cached:
                    results[global_idx] = cached
                    global_idx += 1
                    continue
            batch_items.append({
                "type": el.type, "content": el.content,
                "page_number": el.page_number, "bbox": el.bbox,
                "global_idx": global_idx,
            })
            global_idx += 1
        if batch_items:
            work_items.append((batch_items, source_lang, target_lang, effort))

    if not work_items:
        return results

    with Pool(processes=min(workers, len(work_items))) as pool:
        for batch_results in pool.map(_worker_translate, work_items):
            for gidx, translated, original in batch_results:
                results[gidx] = translated
                if cache:
                    cache.put(original, source_lang, target_lang, translated)

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_translator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/translator.py tests/test_translator.py
git commit -m "feat: parallel codex translator with retry and cache"
```

---

### Task 6: Markdown Builder

**Files:**
- Create: `pdf_translator/md_builder.py`
- Create: `tests/test_md_builder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_md_builder.py
from pdf_translator.extractor import Element
from pdf_translator.md_builder import build_markdown


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
    assert "---" in md  # page break marker


def test_untranslated_fallback():
    elements = [_el("paragraph", "Original")]
    translations = {}  # no translation
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
    assert "---" in md  # separator row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_md_builder.py -v`
Expected: FAIL

- [ ] **Step 3: Implement markdown builder**

```python
# pdf_translator/md_builder.py
from __future__ import annotations

from pdf_translator.extractor import Element

HEADING_LEVELS = {
    "h1": "#", "h2": "##", "h3": "###",
    "h4": "####", "h5": "#####", "h6": "######",
    "Title": "#", "Subtitle": "##",
}


def _render_table(rows: list[list[str]]) -> list[str]:
    """Render a 2D list of strings as a GFM table."""
    if not rows:
        return []
    # Calculate column widths
    num_cols = max(len(r) for r in rows)
    widths = [0] * num_cols
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    widths = [max(w, 3) for w in widths]

    lines: list[str] = []
    for row_idx, row in enumerate(rows):
        padded = [cell.ljust(widths[i]) if i < len(row) else " " * widths[i]
                  for i, cell in enumerate(row + [""] * (num_cols - len(row)))]
        lines.append("| " + " | ".join(padded) + " |")
        if row_idx == 0:
            lines.append("| " + " | ".join("-" * w for w in widths) + " |")
    return lines


def build_markdown(elements: list[Element], translations: dict[int, str]) -> str:
    """Build a Markdown string from elements and their translations."""
    lines: list[str] = []
    current_page = 0

    # Collect table rows: consecutive "table cell" elements form a table
    table_buffer: list[list[str]] = []
    table_row: list[str] = []

    def flush_table():
        nonlocal table_buffer, table_row
        if table_row:
            table_buffer.append(table_row)
            table_row = []
        if table_buffer:
            lines.extend(_render_table(table_buffer))
            lines.append("")
            table_buffer = []

    for idx, el in enumerate(elements):
        # Page separator
        if el.page_number != current_page:
            flush_table()
            if current_page > 0:
                lines.append("")
                lines.append("---")
                lines.append("")
            current_page = el.page_number

        text = translations.get(idx, el.content)

        if el.type == "heading":
            flush_table()
            prefix = HEADING_LEVELS.get(el.level or "h1", "#")
            lines.append(f"{prefix} {text}")
            lines.append("")
        elif el.type == "paragraph":
            flush_table()
            lines.append(text)
            lines.append("")
        elif el.type == "list item":
            flush_table()
            lines.append(f"- {text}")
        elif el.type == "caption":
            flush_table()
            lines.append(f"*{text}*")
            lines.append("")
        elif el.type == "table cell":
            table_row.append(text)
        elif el.type == "table row end":
            table_buffer.append(table_row)
            table_row = []
        else:
            flush_table()
            lines.append(text)
            lines.append("")

    flush_table()
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_md_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/md_builder.py tests/test_md_builder.py
git commit -m "feat: markdown builder with structure preservation"
```

---

### Task 7: PDF Builder — Layout-Preserving Overlay

**Files:**
- Create: `pdf_translator/pdf_builder.py`
- Create: `tests/test_pdf_builder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pdf_builder.py
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from pdf_translator.extractor import Element
from pdf_translator.pdf_builder import build_pdf


def _create_test_pdf(path: str, text: str = "Hello World") -> None:
    """Create a minimal PDF for testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), text, fontsize=12)
    doc.save(path)
    doc.close()


def test_build_pdf_creates_file():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "input.pdf")
        dst = str(Path(d) / "output.pdf")
        _create_test_pdf(src)

        elements = [
            Element(
                type="paragraph", content="Hello World", page_number=1,
                bbox=[72, 88, 200, 104], font_size=12.0,
            )
        ]
        translations = {0: "안녕 세계"}

        build_pdf(src, dst, elements, translations)
        assert Path(dst).exists()
        assert Path(dst).stat().st_size > 0


def test_build_pdf_contains_translated_text():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "input.pdf")
        dst = str(Path(d) / "output.pdf")
        _create_test_pdf(src)

        elements = [
            Element(
                type="paragraph", content="Hello World", page_number=1,
                bbox=[72, 88, 200, 104], font_size=12.0,
            )
        ]
        translations = {0: "안녕 세계"}
        build_pdf(src, dst, elements, translations)

        doc = fitz.open(dst)
        page_text = doc[0].get_text()
        doc.close()
        assert "안녕" in page_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf_builder.py -v`
Expected: FAIL

- [ ] **Step 3: Implement PDF builder**

```python
# pdf_translator/pdf_builder.py
from __future__ import annotations

import shutil
from pathlib import Path

import fitz  # PyMuPDF

from pdf_translator.extractor import Element

# CJK font: try common system locations, fall back to fitz built-in
CJK_FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _find_cjk_font() -> str | None:
    for p in CJK_FONT_PATHS:
        if Path(p).exists():
            return p
    return None


def _fit_fontsize(text: str, rect: fitz.Rect, max_size: float) -> float:
    """Binary search for the largest font size that fits the rect width."""
    lo, hi = 4.0, max_size
    for _ in range(10):
        mid = (lo + hi) / 2
        # Rough estimate: each char ~ 0.6 * font_size wide for CJK
        estimated_width = len(text) * mid * 0.6
        if estimated_width <= rect.width:
            lo = mid
        else:
            hi = mid
    return lo


def build_pdf(
    src_path: str,
    dst_path: str,
    elements: list[Element],
    translations: dict[int, str],
) -> None:
    """Overlay translated text onto a copy of the source PDF."""
    shutil.copy2(src_path, dst_path)
    doc = fitz.open(dst_path)

    cjk_font = _find_cjk_font()

    # Group elements by page
    by_page: dict[int, list[tuple[int, Element]]] = {}
    for idx, el in enumerate(elements):
        if idx in translations:
            by_page.setdefault(el.page_number, []).append((idx, el))

    for page_num, items in by_page.items():
        if page_num < 1 or page_num > len(doc):
            continue
        page = doc[page_num - 1]

        for idx, el in items:
            bbox = el.bbox
            if len(bbox) != 4:
                continue

            # opendataloader bbox: [left, bottom, right, top] in PDF points
            # PyMuPDF Rect: (x0, y0, x1, y1) where y0 < y1 (top-left origin)
            page_height = page.rect.height
            x0, y_bottom, x1, y_top = bbox
            rect = fitz.Rect(x0, page_height - y_top, x1, page_height - y_bottom)

            # Cover original text with white rectangle
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=None, fill=(1, 1, 1))
            shape.commit()

            # Insert translated text
            translated = translations[idx]
            fontsize = _fit_fontsize(translated, rect, el.font_size)

            try:
                if cjk_font:
                    page.insert_text(
                        rect.tl + fitz.Point(0, fontsize),
                        translated,
                        fontsize=fontsize,
                        fontfile=cjk_font,
                        fontname="CJK",
                    )
                else:
                    # Use PyMuPDF built-in CJK support
                    page.insert_text(
                        rect.tl + fitz.Point(0, fontsize),
                        translated,
                        fontsize=fontsize,
                        fontname="china-s",  # built-in simplified Chinese
                    )
            except Exception:
                # Fallback: insert without specific font
                page.insert_text(
                    rect.tl + fitz.Point(0, fontsize),
                    translated,
                    fontsize=fontsize,
                )

    doc.save(dst_path)
    doc.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pdf_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/pdf_builder.py tests/test_pdf_builder.py
git commit -m "feat: PDF builder with CJK font overlay"
```

---

### Task 8: CLI Entry Point — Pipeline Orchestration

**Files:**
- Create: `pdf_translator/cli.py`

- [ ] **Step 1: Implement CLI with full pipeline**

```python
# pdf_translator/cli.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from pdf_translator.config import TranslatorConfig
from pdf_translator.extractor import extract_pdf
from pdf_translator.chunker import build_batches
from pdf_translator.cache import TranslationCache
from pdf_translator.translator import translate_all
from pdf_translator.pdf_builder import build_pdf
from pdf_translator.md_builder import build_markdown

console = Console()


def parse_args(argv: list[str] | None = None) -> TranslatorConfig:
    parser = argparse.ArgumentParser(
        prog="pdf-translator",
        description="Translate PDF documents using Codex CLI",
    )
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    parser.add_argument("--workers", type=int, default=4, help="Parallel processes")
    parser.add_argument("--source-lang", default="en", help="Source language code")
    parser.add_argument("--target-lang", default="ko", help="Target language code")
    parser.add_argument("--effort", default="low", help="Codex reasoning effort")
    parser.add_argument("--pages", default=None, help="Pages to process (e.g. 1,3,5-7)")
    parser.add_argument("--no-cache", action="store_true", help="Disable translation cache")

    args = parser.parse_args(argv)
    return TranslatorConfig(
        input_path=args.input,
        output_dir=args.output_dir,
        workers=args.workers,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        effort=args.effort,
        pages=args.pages,
        use_cache=not args.no_cache,
    )


def run(cfg: TranslatorConfig) -> None:
    input_path = Path(cfg.input_path)
    if not input_path.exists():
        console.print(f"[red]Error: {input_path} not found[/red]")
        sys.exit(1)

    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    with Progress(
        SpinnerColumn(), TextColumn("[bold]{task.description}"), BarColumn(),
        console=console,
    ) as progress:
        # Phase 1: Extract
        task = progress.add_task("Extracting PDF...", total=4)
        elements = extract_pdf(str(input_path), pages=cfg.pages)
        console.print(f"  Extracted [cyan]{len(elements)}[/cyan] text elements")
        progress.update(task, advance=1)

        # Phase 2: Chunk
        progress.update(task, description="Building batches...")
        batches = build_batches(elements)
        console.print(f"  Created [cyan]{len(batches)}[/cyan] translation batches")
        progress.update(task, advance=1)

        # Phase 3: Translate
        progress.update(task, description=f"Translating ({cfg.workers} workers)...")
        cache = None
        if cfg.use_cache:
            cache = TranslationCache(output_dir / "cache.db")

        translations = translate_all(
            batches,
            source_lang=cfg.source_lang,
            target_lang=cfg.target_lang,
            effort=cfg.effort,
            workers=cfg.workers,
            cache=cache,
        )
        console.print(f"  Translated [cyan]{len(translations)}[/cyan] segments")
        progress.update(task, advance=1)

        # Phase 4: Output
        progress.update(task, description="Generating output...")

        # PDF
        pdf_out = str(output_dir / f"{stem}_translated.pdf")
        build_pdf(str(input_path), pdf_out, elements, translations)
        console.print(f"  PDF: [green]{pdf_out}[/green]")

        # Markdown
        md_out = output_dir / f"{stem}_translated.md"
        md_content = build_markdown(elements, translations)
        md_out.write_text(md_content, encoding="utf-8")
        console.print(f"  Markdown: [green]{md_out}[/green]")

        progress.update(task, advance=1)

        if cache:
            cache.close()

    console.print("[bold green]Done![/bold green]")


def main():
    cfg = parse_args()
    run(cfg)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test CLI arg parsing manually**

Run: `cd /Users/babyworm/work/pdf_translator && python -c "from pdf_translator.cli import parse_args; cfg = parse_args(['test.pdf', '--workers', '8']); print(cfg)"`
Expected: `TranslatorConfig(input_path='test.pdf', ..., workers=8, ...)`

- [ ] **Step 3: Commit**

```bash
git add pdf_translator/cli.py
git commit -m "feat: CLI entry point with full pipeline orchestration"
```

---

### Task 9: Integration Test — End-to-End Smoke Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
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

        # Mock extractor to avoid Java/opendataloader-pdf dependency
        from pdf_translator.extractor import Element
        mock_elements = [
            Element(type="heading", content="Introduction", page_number=1,
                    bbox=[72, 90, 200, 110], font_size=18.0, level="h1"),
            Element(type="paragraph", content="This is a test document.", page_number=1,
                    bbox=[72, 130, 500, 150], font_size=12.0),
            Element(type="paragraph", content="It has multiple sentences.", page_number=1,
                    bbox=[72, 150, 500, 170], font_size=12.0),
        ]

        # Mock codex to return simple "translations"
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

        with patch("pdf_translator.extractor.extract_pdf", return_value=mock_elements), \
             patch("pdf_translator.translator._run_codex", side_effect=mock_run_codex):
            run(cfg)

        out_dir = Path(d) / "output"
        assert (out_dir / "test_translated.pdf").exists()
        assert (out_dir / "test_translated.md").exists()

        # Check markdown has translated content
        md_content = (out_dir / "test_translated.md").read_text()
        assert "[KO]" in md_content
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: end-to-end integration smoke test"
```

---

### Task 10: Final Polish

- [ ] **Step 1: Create .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
output/
*.db
.omc/
```

- [ ] **Step 2: Verify entry point works**

Run: `cd /Users/babyworm/work/pdf_translator && python -m pdf_translator.cli --help`
Expected: Help text with all arguments shown

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add gitignore and finalize project"
```
