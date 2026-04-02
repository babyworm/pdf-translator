# LLM Layout QA — Design Spec

**Date**: 2026-04-03
**Status**: Approved
**Scope**: Pre-build Layout Review + Post-build QA with auto-retry loop

## Decisions

| Item | Decision |
|------|----------|
| Scope | Pre-build + Post-build, both |
| Cost management | Rule-based anomaly detection first, LLM only for flagged items |
| QA failure action | Auto re-translate + re-build |
| Retry limit | `--qa-retries N`, default 2 |
| QA default | ON by default, `--no-qa` to disable |
| Pipeline approach | Inline in `run()`, single command |

---

## 1. Pre-build Layout Review

**When**: After translation, before PDF build.

### Rule-based anomaly detection (Python, no LLM call)

- Translated text > 2x original length AND bbox area is small → overflow risk
- Translation is empty or identical to original → translation failure
- Heading translation exceeds 150% of bbox width → heading overflow

### LLM review (only for flagged items)

**Input:**
```json
[
  {
    "index": 3,
    "original": "Attention Is All You Need",
    "translated": "어텐션이 당신이 필요한 전부입니다",
    "type": "heading",
    "bbox_w": 188, "bbox_h": 22,
    "issue": "translated text likely overflows bbox"
  }
]
```

**Output:**
```json
[
  {
    "index": 3,
    "action": "revise",
    "text": "Attention Is All You Need",
    "reason": "paper title should be kept as original"
  }
]
```

**Actions:** `"keep"` (use current translation), `"revise"` (use new text), `"skip"` (keep original, don't overlay)

---

## 2. Post-build QA

**When**: After PDF build.

### Rule-based anomaly detection (Python, no LLM call)

- Extract text from built PDF via pypdf
- Compare expected segment count per page vs extracted count → missing segments
- Detect blank pages that should have translations
- Detect original-language text still visible (white-out failure)

### LLM review (only for flagged pages)

**Input:**
```json
{
  "page": 2,
  "expected_segments": 13,
  "extracted_text": "순환 신경망, 특히 long short-term...",
  "original_text": "Recurrent neural networks, long short-term...",
  "issues": ["original text still visible", "only 8 of 13 segments found"]
}
```

**Output:**
```json
{
  "page": 2,
  "verdict": "fail",
  "failed_indices": [5, 8, 11],
  "reason": "3 segments missing, likely formula overlap causing text displacement"
}
```

**Verdicts:** `"pass"` (no issues), `"fail"` (re-translate needed, includes `failed_indices`)

---

## 3. Auto Re-translate Loop

### Pipeline flow

```
Extract → Translate → Pre-build Review → PDF Build → Post-build QA
                          ↑                              │
                          └──── Re-translate (failed) ←──┘
                               (max --qa-retries times)
```

### Behavior

1. Post-build QA returns `verdict: "fail"` with `failed_indices`
2. Pre-build Review returns `action: "revise"` with new translations
3. Merge both: `revise` applied directly, `fail` indices re-translated (cache bypassed)
4. Re-build PDF
5. Post-build QA again
6. If `--qa-retries` (default 2) exhausted, print remaining issues to console and finish

### Re-translation

- Only failed segments sent to LLM (not full re-translation)
- `revise` responses applied directly (no LLM call needed)
- `fail` re-translation prompt includes previous translation + failure reason
- Cache bypassed for re-translated segments

### CLI

```bash
pdf-translator input.pdf                    # QA on (default)
pdf-translator input.pdf --no-qa            # QA disabled
pdf-translator input.pdf --qa-retries 3     # retry up to 3 times
pdf-translator input.pdf --qa-retries 0     # QA runs but no retry (report only)
```

---

## 4. File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `pdf_translator/core/qa.py` | Create | Rule-based detection + LLM review wrappers |
| `pdf_translator/core/translator/base.py` | Modify | Add QA prompt builders |
| `pdf_translator/cli/main.py` | Modify | Add `--no-qa`, `--qa-retries`, retry loop |
| `pdf_translator/core/config.py` | Modify | Add `no_qa`, `qa_retries` to TranslatorConfig |
| `tests/test_qa.py` | Create | Tests for detection + review |

### `qa.py` functions

```python
# Rule-based anomaly detection
def detect_pre_build_issues(elements, translations) -> list[dict]
def detect_post_build_issues(src_pdf, built_pdf, elements, translations) -> list[dict]

# LLM review (called only when issues detected)
def review_pre_build(issues, backend, source_lang, target_lang) -> list[dict]
def review_post_build(issues, backend, source_lang, target_lang) -> list[dict]

# Merge results into re-translate targets
def collect_retranslate_indices(pre_results, post_results) -> set[int]
```

---

## Out of Scope

- Visual (screenshot-based) QA — text-level only for now
- Per-character layout precision — focus on segment-level completeness
- QA review uses the best available LLM backend (auto-select: claude-cli > codex > gemini-cli), regardless of which backend was used for translation. If no LLM backend is available, QA runs rule-based detection only (no LLM review, no revise — report issues and continue).
