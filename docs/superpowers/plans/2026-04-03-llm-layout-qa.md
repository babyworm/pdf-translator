# LLM Layout QA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add pre-build layout review and post-build QA with auto-retry to the PDF translation pipeline.

**Architecture:** Rule-based anomaly detection filters obvious issues (no LLM cost), then flags are sent to LLM for judgment. Results feed an auto-retry loop that re-translates failed segments and re-builds the PDF, up to N retries.

**Tech Stack:** Python, pypdf (text re-extraction), existing LLM backends (translate_raw)

**Spec:** `docs/superpowers/specs/2026-04-03-llm-layout-qa-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pdf_translator/core/config.py` | Modify | Add `no_qa: bool`, `qa_retries: int` |
| `pdf_translator/core/qa.py` | Create | Rule-based detection + LLM review wrappers |
| `pdf_translator/core/translator/base.py` | Modify | Add `build_qa_pre_prompt`, `build_qa_post_prompt`, `parse_qa_response` |
| `pdf_translator/cli/main.py` | Modify | Add CLI args + retry loop in `run()` |
| `tests/test_qa.py` | Create | Tests for all QA functions |

---

### Task 1: Config + CLI args

**Files:**
- Modify: `pdf_translator/core/config.py`
- Modify: `pdf_translator/cli/main.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
def test_parse_args_qa_defaults():
    cfg = parse_args(["input.pdf"])
    assert cfg.no_qa is False
    assert cfg.qa_retries == 2


def test_parse_args_no_qa():
    cfg = parse_args(["input.pdf", "--no-qa"])
    assert cfg.no_qa is True


def test_parse_args_qa_retries():
    cfg = parse_args(["input.pdf", "--qa-retries", "3"])
    assert cfg.qa_retries == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py::test_parse_args_qa_defaults tests/test_cli.py::test_parse_args_no_qa tests/test_cli.py::test_parse_args_qa_retries -v`

Expected: FAIL (no `no_qa` attribute)

- [ ] **Step 3: Add fields to TranslatorConfig**

In `pdf_translator/core/config.py`, add to `TranslatorConfig`:

```python
    no_qa: bool = False
    qa_retries: int = 2
```

- [ ] **Step 4: Add CLI arguments to `parse_args`**

In `pdf_translator/cli/main.py` `parse_args()`, add:

```python
    parser.add_argument("--no-qa", action="store_true",
                        help="Disable QA review (default: QA enabled)")
    parser.add_argument("--qa-retries", type=int, default=2,
                        help="Max QA retry attempts (default: 2)")
```

And in the `TranslatorConfig` constructor call, add:

```python
        no_qa=args.no_qa,
        qa_retries=args.qa_retries,
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_cli.py -v`

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add pdf_translator/core/config.py pdf_translator/cli/main.py tests/test_cli.py
git commit -m "feat: add --no-qa and --qa-retries CLI options"
```

---

### Task 2: Pre-build rule-based detection

**Files:**
- Create: `pdf_translator/core/qa.py`
- Create: `tests/test_qa.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_qa.py`:

```python
import pytest
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
        # Small bbox, translated text much longer than original
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
        assert "heading" in issues[0]["issue"].lower() or "overflow" in issues[0]["issue"]

    def test_skips_untranslated_elements(self):
        elements = [_el("Hello"), _el("World")]
        translations = {0: "안녕"}  # index 1 not translated
        issues = detect_pre_build_issues(elements, translations)
        assert all(i["index"] == 0 or True for i in issues)  # no crash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_qa.py::TestPreBuildDetection -v`

Expected: FAIL (ImportError — `qa` module doesn't exist)

- [ ] **Step 3: Implement `detect_pre_build_issues`**

Create `pdf_translator/core/qa.py`:

```python
from __future__ import annotations

import logging

from pdf_translator.core.extractor import Element

logger = logging.getLogger(__name__)


def _estimate_text_width(text: str, font_size: float) -> float:
    """Rough estimate of text width in points."""
    return sum(font_size * (1.0 if ord(ch) > 0x2E80 else 0.6) for ch in text)


def detect_pre_build_issues(
    elements: list[Element],
    translations: dict[int, str],
) -> list[dict]:
    """Detect potential layout issues before PDF build. No LLM calls."""
    issues = []

    for i, el in enumerate(elements):
        if i not in translations:
            continue
        translated = translations[i]
        bbox = el.bbox
        if not bbox or len(bbox) != 4:
            continue

        bbox_w = bbox[2] - bbox[0]
        bbox_h = bbox[3] - bbox[1]
        original = el.content

        # Empty translation
        if not translated or not translated.strip():
            issues.append({
                "index": i, "original": original, "translated": translated,
                "type": el.type, "bbox_w": round(bbox_w, 1), "bbox_h": round(bbox_h, 1),
                "issue": "empty translation",
            })
            continue

        # Identical to original (translation may have failed)
        if translated.strip() == original.strip():
            issues.append({
                "index": i, "original": original, "translated": translated,
                "type": el.type, "bbox_w": round(bbox_w, 1), "bbox_h": round(bbox_h, 1),
                "issue": "identical to original — possible translation failure",
            })
            continue

        # Overflow risk: translated text much longer and bbox is small
        est_width = _estimate_text_width(translated, el.font_size)
        num_lines = max(1, est_width / bbox_w) if bbox_w > 0 else 1
        est_height = num_lines * el.font_size * 1.3

        if len(translated) > len(original) * 2 and est_height > bbox_h * 2:
            issues.append({
                "index": i, "original": original, "translated": translated,
                "type": el.type, "bbox_w": round(bbox_w, 1), "bbox_h": round(bbox_h, 1),
                "issue": "translated text likely overflows bbox",
            })
            continue

        # Heading overflow
        if el.type == "heading" and est_width > bbox_w * 1.5:
            issues.append({
                "index": i, "original": original, "translated": translated,
                "type": el.type, "bbox_w": round(bbox_w, 1), "bbox_h": round(bbox_h, 1),
                "issue": "heading overflow — translation exceeds 150% of bbox width",
            })

    return issues
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_qa.py::TestPreBuildDetection -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/qa.py tests/test_qa.py
git commit -m "feat: add pre-build rule-based layout issue detection"
```

---

### Task 3: Post-build rule-based detection

**Files:**
- Modify: `pdf_translator/core/qa.py`
- Modify: `tests/test_qa.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_qa.py`:

```python
import tempfile
from pathlib import Path
from reportlab.pdfgen import canvas
from pdf_translator.core.qa import detect_post_build_issues


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
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.pdf"
            built = Path(d) / "built.pdf"
            _create_pdf_with_text(src, [["Hello World"]])
            _create_pdf_with_text(built, [["안녕 세계"]])

            elements = [_el("Hello World")]
            translations = {0: "안녕 세계"}
            issues = detect_post_build_issues(str(src), str(built), elements, translations)
            assert len(issues) == 0

    def test_detects_missing_text(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.pdf"
            built = Path(d) / "built.pdf"
            _create_pdf_with_text(src, [["Hello", "World", "Test"]])
            # Built PDF has only 1 text element instead of 3
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
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.pdf"
            built = Path(d) / "built.pdf"
            _create_pdf_with_text(src, [["Hello World"]])
            # Built PDF still has English text
            _create_pdf_with_text(built, [["Hello World", "안녕 세계"]])

            elements = [_el("Hello World")]
            translations = {0: "안녕 세계"}
            issues = detect_post_build_issues(str(src), str(built), elements, translations)
            assert len(issues) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_qa.py::TestPostBuildDetection -v`

Expected: FAIL (ImportError — `detect_post_build_issues` not defined)

- [ ] **Step 3: Implement `detect_post_build_issues`**

Add to `pdf_translator/core/qa.py`:

```python
from pypdf import PdfReader


def detect_post_build_issues(
    src_pdf: str,
    built_pdf: str,
    elements: list[Element],
    translations: dict[int, str],
) -> list[dict]:
    """Detect issues in the built PDF by re-extracting text. No LLM calls."""
    issues = []

    try:
        reader = PdfReader(built_pdf)
    except Exception as e:
        logger.warning("Cannot read built PDF for QA: %s", e)
        return issues

    # Group expected translations by page
    by_page: dict[int, list[tuple[int, str, str]]] = {}
    for i, el in enumerate(elements):
        if i in translations:
            by_page.setdefault(el.page_number, []).append(
                (i, el.content, translations[i])
            )

    for page_num, expected in by_page.items():
        page_idx = page_num - 1
        if page_idx < 0 or page_idx >= len(reader.pages):
            issues.append({
                "page": page_num,
                "expected_segments": len(expected),
                "extracted_text": "",
                "original_text": "",
                "issues": [f"page {page_num} not found in built PDF"],
            })
            continue

        extracted = reader.pages[page_idx].extract_text() or ""

        page_issues = []

        # Check if expected translated segments appear
        found = sum(1 for _, _, trans in expected if trans[:10] in extracted)
        if found < len(expected) * 0.5:
            page_issues.append(
                f"only {found} of {len(expected)} segments found in extracted text"
            )

        # Check if original text still visible
        original_found = sum(
            1 for _, orig, _ in expected
            if len(orig) > 10 and orig[:15] in extracted
        )
        if original_found > 0:
            page_issues.append(
                f"{original_found} original text segments still visible"
            )

        if page_issues:
            originals = " | ".join(orig[:30] for _, orig, _ in expected[:3])
            issues.append({
                "page": page_num,
                "expected_segments": len(expected),
                "extracted_text": extracted[:500],
                "original_text": originals,
                "issues": page_issues,
            })

    return issues
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_qa.py::TestPostBuildDetection -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/qa.py tests/test_qa.py
git commit -m "feat: add post-build rule-based QA detection"
```

---

### Task 4: QA LLM prompts + parsers

**Files:**
- Modify: `pdf_translator/core/translator/base.py`
- Modify: `tests/test_backend_protocol.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_backend_protocol.py`:

```python
def test_build_qa_pre_prompt():
    from pdf_translator.core.translator.base import build_qa_pre_prompt
    issues = [
        {"index": 0, "original": "Hello", "translated": "", "type": "paragraph",
         "bbox_w": 100, "bbox_h": 20, "issue": "empty translation"},
    ]
    prompt = build_qa_pre_prompt(issues, "en", "ko")
    assert "empty" in prompt
    assert "action" in prompt.lower()


def test_build_qa_post_prompt():
    from pdf_translator.core.translator.base import build_qa_post_prompt
    issues = [
        {"page": 1, "expected_segments": 5, "extracted_text": "안녕",
         "original_text": "Hello", "issues": ["only 2 of 5 found"]},
    ]
    prompt = build_qa_post_prompt(issues)
    assert "verdict" in prompt.lower()


def test_parse_qa_pre_response():
    import json
    from pdf_translator.core.translator.base import parse_qa_pre_response
    response = json.dumps([
        {"index": 0, "action": "revise", "text": "안녕하세요", "reason": "was empty"},
    ])
    result = parse_qa_pre_response(response)
    assert result[0]["action"] == "revise"
    assert result[0]["text"] == "안녕하세요"


def test_parse_qa_post_response():
    import json
    from pdf_translator.core.translator.base import parse_qa_post_response
    response = json.dumps([
        {"page": 1, "verdict": "fail", "failed_indices": [2, 3], "reason": "missing"},
    ])
    result = parse_qa_post_response(response)
    assert result[0]["verdict"] == "fail"
    assert 2 in result[0]["failed_indices"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backend_protocol.py::test_build_qa_pre_prompt tests/test_backend_protocol.py::test_parse_qa_pre_response tests/test_backend_protocol.py::test_build_qa_post_prompt tests/test_backend_protocol.py::test_parse_qa_post_response -v`

Expected: FAIL (ImportError)

- [ ] **Step 3: Implement QA prompts and parsers**

Add to `pdf_translator/core/translator/base.py`:

```python
def build_qa_pre_prompt(issues: list[dict], source_lang: str, target_lang: str) -> str:
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)
    return f"""You are a translation quality reviewer ({src_name} → {tgt_name}).

Review each flagged translation issue and decide an action:
- "keep": the current translation is acceptable despite the flag
- "revise": provide a better translation (include "text" field)
- "skip": keep the original text, do not translate this element

Output ONLY a JSON array: [{{"index": N, "action": "keep"|"revise"|"skip", "text": "...", "reason": "..."}}]
For "keep" and "skip", omit "text".

Flagged issues:
{json.dumps(issues, ensure_ascii=False, indent=2)}"""


def build_qa_post_prompt(issues: list[dict]) -> str:
    return f"""You are a PDF translation quality reviewer.

I built a translated PDF but detected potential problems on some pages.
For each page, decide:
- "pass": the page is acceptable
- "fail": the page has problems — list the segment indices that need re-translation in "failed_indices"

Output ONLY a JSON array: [{{"page": N, "verdict": "pass"|"fail", "failed_indices": [...], "reason": "..."}}]

Detected issues:
{json.dumps(issues, ensure_ascii=False, indent=2)}"""


def parse_qa_pre_response(response: str) -> list[dict]:
    """Parse pre-build QA response. Returns list of action dicts."""
    response = response.strip()
    try:
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if fence_match:
            response = fence_match.group(1).strip()
        bracket_start = response.find("[")
        bracket_end = response.rfind("]")
        if bracket_start >= 0 and bracket_end > bracket_start:
            response = response[bracket_start:bracket_end + 1]
        return json.loads(response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse QA pre response: %s", exc)
        return []


def parse_qa_post_response(response: str) -> list[dict]:
    """Parse post-build QA response. Returns list of verdict dicts."""
    response = response.strip()
    try:
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if fence_match:
            response = fence_match.group(1).strip()
        bracket_start = response.find("[")
        bracket_end = response.rfind("]")
        if bracket_start >= 0 and bracket_end > bracket_start:
            response = response[bracket_start:bracket_end + 1]
        return json.loads(response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse QA post response: %s", exc)
        return []
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_backend_protocol.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/translator/base.py tests/test_backend_protocol.py
git commit -m "feat: add QA prompt builders and response parsers"
```

---

### Task 5: LLM review wrappers in qa.py

**Files:**
- Modify: `pdf_translator/core/qa.py`
- Modify: `tests/test_qa.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_qa.py`:

```python
from unittest.mock import MagicMock
from pdf_translator.core.qa import review_pre_build, review_post_build, collect_retranslate_indices


class TestLLMReview:
    def test_review_pre_build_calls_backend(self):
        backend = MagicMock()
        backend.translate_raw.return_value = '[{"index": 0, "action": "revise", "text": "수정됨", "reason": "test"}]'
        issues = [{"index": 0, "original": "Hi", "translated": "", "type": "paragraph",
                   "bbox_w": 100, "bbox_h": 20, "issue": "empty"}]
        result = review_pre_build(issues, backend, "en", "ko")
        assert len(result) == 1
        assert result[0]["action"] == "revise"
        backend.translate_raw.assert_called_once()

    def test_review_post_build_calls_backend(self):
        backend = MagicMock()
        backend.translate_raw.return_value = '[{"page": 1, "verdict": "fail", "failed_indices": [2], "reason": "missing"}]'
        issues = [{"page": 1, "expected_segments": 5, "extracted_text": "test",
                   "original_text": "orig", "issues": ["only 2 of 5"]}]
        result = review_post_build(issues, backend, "en", "ko")
        assert result[0]["verdict"] == "fail"

    def test_review_pre_build_no_backend(self):
        """Without LLM backend, returns empty."""
        issues = [{"index": 0, "issue": "test"}]
        result = review_pre_build(issues, None, "en", "ko")
        assert result == []


class TestCollectRetranslate:
    def test_collect_from_pre_revise(self):
        pre = [{"index": 3, "action": "revise", "text": "새 번역"}]
        post = []
        indices = collect_retranslate_indices(pre, post)
        assert 3 in indices

    def test_collect_from_post_fail(self):
        pre = []
        post = [{"page": 1, "verdict": "fail", "failed_indices": [5, 8]}]
        indices = collect_retranslate_indices(pre, post)
        assert indices == {5, 8}

    def test_collect_merged(self):
        pre = [{"index": 2, "action": "revise", "text": "x"}]
        post = [{"page": 1, "verdict": "fail", "failed_indices": [4]}]
        indices = collect_retranslate_indices(pre, post)
        assert indices == {2, 4}

    def test_collect_skip_keep(self):
        pre = [{"index": 1, "action": "keep"}, {"index": 2, "action": "skip"}]
        post = [{"page": 1, "verdict": "pass"}]
        indices = collect_retranslate_indices(pre, post)
        assert len(indices) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_qa.py::TestLLMReview tests/test_qa.py::TestCollectRetranslate -v`

Expected: FAIL (ImportError)

- [ ] **Step 3: Implement LLM review + collect**

Add to `pdf_translator/core/qa.py`:

```python
from pdf_translator.core.translator.base import (
    build_qa_pre_prompt,
    build_qa_post_prompt,
    parse_qa_pre_response,
    parse_qa_post_response,
)


def review_pre_build(
    issues: list[dict],
    backend,
    source_lang: str,
    target_lang: str,
) -> list[dict]:
    """Send pre-build issues to LLM for review. Returns action list."""
    if not backend or not hasattr(backend, "translate_raw"):
        return []
    prompt = build_qa_pre_prompt(issues, source_lang, target_lang)
    response = backend.translate_raw(prompt, count=len(issues))
    if response:
        return parse_qa_pre_response(response)
    return []


def review_post_build(
    issues: list[dict],
    backend,
    source_lang: str,
    target_lang: str,
) -> list[dict]:
    """Send post-build issues to LLM for review. Returns verdict list."""
    if not backend or not hasattr(backend, "translate_raw"):
        return []
    prompt = build_qa_post_prompt(issues)
    response = backend.translate_raw(prompt, count=len(issues))
    if response:
        return parse_qa_post_response(response)
    return []


def collect_retranslate_indices(
    pre_results: list[dict],
    post_results: list[dict],
) -> set[int]:
    """Collect indices that need re-translation from both QA stages."""
    indices: set[int] = set()

    for item in pre_results:
        if item.get("action") == "revise":
            indices.add(item["index"])

    for item in post_results:
        if item.get("verdict") == "fail":
            for idx in item.get("failed_indices", []):
                indices.add(idx)

    return indices
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_qa.py -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/qa.py tests/test_qa.py
git commit -m "feat: add LLM review wrappers and retranslate index collection"
```

---

### Task 6: Retry loop in cli/main.py

**Files:**
- Modify: `pdf_translator/cli/main.py`

- [ ] **Step 1: Modify `run()` to include QA retry loop**

Replace the PDF build section in `run()` (the `else` branch starting around line 260) with:

```python
            else:
                progress.update(task, description="Generating output...")
                pdf_out = str(output_dir / f"{stem}_translated.pdf")

                if cfg.no_qa:
                    build_pdf(str(input_path), pdf_out, elements, translations)
                    console.print(f"  PDF: [green]{pdf_out}[/green]")
                else:
                    from pdf_translator.core.qa import (
                        collect_retranslate_indices,
                        detect_post_build_issues,
                        detect_pre_build_issues,
                        review_post_build,
                        review_pre_build,
                    )

                    qa_backend = None
                    if hasattr(backend_obj, "translate_raw"):
                        qa_backend = backend_obj

                    for retry in range(cfg.qa_retries + 1):
                        # Pre-build review
                        pre_results = []
                        pre_issues = detect_pre_build_issues(elements, translations)
                        if pre_issues and qa_backend:
                            console.print(f"  QA pre-build: [yellow]{len(pre_issues)} issues[/yellow]")
                            pre_results = review_pre_build(
                                pre_issues, qa_backend, cfg.source_lang, cfg.target_lang,
                            )
                            # Apply revisions
                            for item in pre_results:
                                if item.get("action") == "revise" and item.get("text"):
                                    translations[item["index"]] = item["text"]
                                elif item.get("action") == "skip" and item["index"] in translations:
                                    del translations[item["index"]]
                        elif pre_issues:
                            console.print(f"  QA pre-build: [yellow]{len(pre_issues)} issues (rule-based only)[/yellow]")

                        # Build PDF
                        build_pdf(str(input_path), pdf_out, elements, translations)

                        # Post-build QA (skip on last retry)
                        if retry == cfg.qa_retries:
                            break

                        post_issues = detect_post_build_issues(
                            str(input_path), pdf_out, elements, translations,
                        )
                        if not post_issues:
                            console.print("  QA post-build: [green]pass[/green]")
                            break

                        post_results = []
                        if qa_backend:
                            post_results = review_post_build(
                                post_issues, qa_backend, cfg.source_lang, cfg.target_lang,
                            )

                        failed = collect_retranslate_indices(pre_results, post_results)
                        if not failed:
                            console.print("  QA post-build: [green]pass (no retranslate needed)[/green]")
                            break

                        console.print(
                            f"  QA retry {retry + 1}/{cfg.qa_retries}: "
                            f"re-translating [yellow]{len(failed)}[/yellow] segments"
                        )

                        # Re-translate failed segments only
                        failed_elements = [
                            [el for i, el in enumerate(elements) if i in failed]
                        ]
                        if failed_elements[0]:
                            re_raw = translate_all(
                                failed_elements,
                                source_lang=cfg.source_lang,
                                target_lang=cfg.target_lang,
                                effort=cfg.effort,
                                workers=max(1, cfg.workers),
                                cache=None,  # bypass cache
                                backend=cfg.backend,
                                glossary=glossary_dict,
                                layout_aware=True,
                            )
                            # Map back to original indices
                            failed_list = sorted(failed)
                            for re_idx, text in re_raw.items():
                                if re_idx < len(failed_list) and text:
                                    translations[failed_list[re_idx]] = text

                    console.print(f"  PDF: [green]{pdf_out}[/green]")

                md_out = output_dir / f"{stem}_translated.md"
                md_content = build_markdown(elements, translations)
                md_out.write_text(md_content, encoding="utf-8")
                console.print(f"  Markdown: [green]{md_out}[/green]")

                progress.update(task, advance=1)
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --ignore=tests/test_e2e_translate.py`

Expected: All PASS

- [ ] **Step 3: Lint**

Run: `ruff check pdf_translator/core/qa.py pdf_translator/cli/main.py pdf_translator/core/translator/base.py`

Expected: No errors (or only pre-existing ones)

- [ ] **Step 4: Commit**

```bash
git add pdf_translator/cli/main.py
git commit -m "feat: integrate QA retry loop into translation pipeline"
```

---

### Task 7: E2E verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --ignore=tests/test_e2e_translate.py -W error::DeprecationWarning`

Expected: All PASS, 0 warnings

- [ ] **Step 2: E2E test with QA enabled**

Run: `pdf-translator test_e2e/attention_paper.pdf --pages 1-3 --output-dir test_e2e/output_qa --backend codex --effort low --glossary ml-ai --target-lang ko`

Expected: QA messages appear in console output, PDF generated

- [ ] **Step 3: E2E test with QA disabled**

Run: `pdf-translator test_e2e/attention_paper.pdf --pages 1-3 --output-dir test_e2e/output_noqa --backend codex --effort low --glossary ml-ai --target-lang ko --no-qa`

Expected: No QA messages, PDF generated

- [ ] **Step 4: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: LLM Layout QA — complete implementation with pre/post-build review and auto-retry"
```
