# Phase 1: Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure pdf_translator into a core/ library with pluggable LLM backends and a rewritten PDF builder that preserves original layout using PyMuPDF's redaction API and insert_htmlbox.

**Architecture:** Existing flat modules move under `pdf_translator/core/`. Translation backends implement a `TranslationBackend` Protocol and are auto-discovered by a Router. PDF builder v2 replaces white-box overlay with redaction + CSS-styled insertion.

**Tech Stack:** Python 3.10+, PyMuPDF (fitz), subprocess (CLI backends), Protocol (typing)

**Spec:** `docs/superpowers/specs/2026-04-01-pdf-translator-v2-design.md` §2, §3, §4

**Phases 2-4 are separate plans** (glossary/draft, OCR, web UI).

---

## File Map

### New files to create

| File | Responsibility |
|------|----------------|
| `pdf_translator/core/__init__.py` | Public API: `translate_pdf()`, re-exports |
| `pdf_translator/core/translator/__init__.py` | Re-export `translate_all` |
| `pdf_translator/core/translator/base.py` | `TranslationBackend` Protocol + `build_prompt()` |
| `pdf_translator/core/translator/router.py` | `BackendRouter`: auto-select + explicit select |
| `pdf_translator/core/translator/backends/__init__.py` | Backend registry |
| `pdf_translator/core/translator/backends/codex_cli.py` | Codex CLI backend |
| `pdf_translator/core/translator/backends/claude_cli.py` | Claude CLI backend |
| `pdf_translator/core/translator/backends/gemini_cli.py` | Gemini CLI backend |
| `pdf_translator/core/translator/backends/google_translate.py` | Google Translate backend |
| `pdf_translator/cli/__init__.py` | Empty init |
| `pdf_translator/cli/main.py` | CLI entry point (moved from cli.py) |
| `tests/test_backend_protocol.py` | Backend Protocol + Router tests |
| `tests/test_pdf_builder_v2.py` | Redaction + htmlbox tests |

### Files to move (old → new)

| From | To | Notes |
|------|----|-------|
| `pdf_translator/config.py` | `pdf_translator/core/config.py` | No changes |
| `pdf_translator/extractor.py` | `pdf_translator/core/extractor.py` | No changes |
| `pdf_translator/chunker.py` | `pdf_translator/core/chunker.py` | No changes |
| `pdf_translator/cache.py` | `pdf_translator/core/cache.py` | No changes |
| `pdf_translator/md_builder.py` | `pdf_translator/core/md_builder.py` | No changes |
| `pdf_translator/pdf_builder.py` | `pdf_translator/core/pdf_builder.py` | Rewritten (Task 8-9) |
| `pdf_translator/translator.py` | Deleted | Split into backends + router |
| `pdf_translator/cli.py` | `pdf_translator/cli/main.py` | Updated imports |

### Files to modify

| File | Changes |
|------|---------|
| `pdf_translator/__init__.py` | Update re-exports |
| `pyproject.toml` | Update entry point to `pdf_translator.cli.main:main` |
| `tests/test_*.py` | Update imports |

---

## Task 1: Core package scaffolding + module migration

**Files:**
- Create: `pdf_translator/core/__init__.py`, `pdf_translator/core/translator/__init__.py`, `pdf_translator/core/translator/backends/__init__.py`, `pdf_translator/cli/__init__.py`
- Move: `config.py`, `extractor.py`, `chunker.py`, `cache.py`, `md_builder.py` → `core/`
- Modify: `pdf_translator/__init__.py`, all `tests/test_*.py`

- [ ] **Step 1: Create core/ directory structure**

```bash
mkdir -p pdf_translator/core/translator/backends
mkdir -p pdf_translator/cli
touch pdf_translator/core/__init__.py
touch pdf_translator/core/translator/__init__.py
touch pdf_translator/core/translator/backends/__init__.py
touch pdf_translator/cli/__init__.py
```

- [ ] **Step 2: Move modules to core/ with git mv**

```bash
git mv pdf_translator/config.py pdf_translator/core/config.py
git mv pdf_translator/extractor.py pdf_translator/core/extractor.py
git mv pdf_translator/chunker.py pdf_translator/core/chunker.py
git mv pdf_translator/cache.py pdf_translator/core/cache.py
git mv pdf_translator/md_builder.py pdf_translator/core/md_builder.py
git mv pdf_translator/pdf_builder.py pdf_translator/core/pdf_builder.py
```

- [ ] **Step 3: Update internal imports in moved modules**

`pdf_translator/core/chunker.py` — change import:
```python
# Before
from pdf_translator.extractor import Element
# After
from pdf_translator.core.extractor import Element
```

Apply the same pattern to `core/cache.py` (no changes needed — no internal imports), `core/md_builder.py`, `core/pdf_builder.py`.

- [ ] **Step 4: Create backward-compat re-exports in pdf_translator/__init__.py**

```python
# pdf_translator/__init__.py
"""PDF Translator — core re-exports for backward compatibility."""
from pdf_translator.core.extractor import Element, extract_pdf, parse_elements
from pdf_translator.core.config import TranslatorConfig
from pdf_translator.core.chunker import build_batches
from pdf_translator.core.cache import TranslationCache
from pdf_translator.core.md_builder import build_markdown
from pdf_translator.core.pdf_builder import build_pdf
```

- [ ] **Step 5: Update all test imports**

For every test file in `tests/`, update imports from `pdf_translator.xxx` to `pdf_translator.core.xxx`. Example for `tests/test_cache.py`:

```python
# Before
from pdf_translator.cache import TranslationCache
# After
from pdf_translator.core.cache import TranslationCache
```

Repeat for: `test_chunker.py`, `test_config.py`, `test_extractor.py`, `test_extractor_table.py`, `test_md_builder.py`, `test_pdf_builder.py`. Leave `test_translator.py`, `test_translate_all.py`, and `test_integration.py` for Task 7 (they depend on the translator rewrite).

- [ ] **Step 6: Run passing tests to verify migration**

```bash
python -m pytest tests/test_cache.py tests/test_chunker.py tests/test_config.py tests/test_extractor.py tests/test_extractor_table.py tests/test_md_builder.py tests/test_pdf_builder.py -v
```

Expected: All PASS (same count as before migration).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: move modules to core/ package structure"
```

---

## Task 2: TranslationBackend Protocol + prompt builder

**Files:**
- Create: `pdf_translator/core/translator/base.py`
- Test: `tests/test_backend_protocol.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backend_protocol.py
from pdf_translator.core.translator.base import (
    TranslationBackend,
    build_prompt,
    parse_response,
)
from pdf_translator.core.extractor import Element


def _el(content: str) -> Element:
    return Element(type="paragraph", content=content, page_number=1, bbox=[0, 0, 100, 20])


def test_build_prompt_contains_text():
    texts = ["Hello", "World"]
    prompt = build_prompt(texts, "en", "ko")
    assert "Hello" in prompt
    assert "Korean" in prompt


def test_build_prompt_with_glossary():
    texts = ["The transformer model"]
    glossary = {"transformer": "트랜스포머"}
    prompt = build_prompt(texts, "en", "ko", glossary=glossary)
    assert "transformer" in prompt
    assert "트랜스포머" in prompt


def test_parse_response_json_array():
    import json
    response = json.dumps([{"index": 0, "text": "안녕"}, {"index": 1, "text": "세계"}])
    result = parse_response(response, count=2)
    assert result == ["안녕", "세계"]


def test_parse_response_plain_lines():
    result = parse_response("안녕\n세계", count=2)
    assert result == ["안녕", "세계"]


def test_parse_response_pads_missing():
    import json
    response = json.dumps([{"index": 0, "text": "안녕"}])
    result = parse_response(response, count=3)
    assert result[0] == "안녕"
    assert result[1] is None
    assert result[2] is None


class FakeBackend:
    name = "fake"
    backend_type = "test"

    def is_available(self) -> bool:
        return True

    def translate(self, texts, source_lang, target_lang, glossary=None):
        return [f"[{target_lang}]{t}" for t in texts]


def test_fake_backend_satisfies_protocol():
    backend = FakeBackend()
    assert isinstance(backend, TranslationBackend)
    result = backend.translate(["Hello"], "en", "ko")
    assert result == ["[ko]Hello"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_backend_protocol.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement base.py**

```python
# pdf_translator/core/translator/base.py
from __future__ import annotations

import json
import logging
import re
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

LANG_NAMES = {
    "en": "English", "ko": "Korean", "ja": "Japanese",
    "zh": "Chinese", "de": "German", "fr": "French",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian",
}


@runtime_checkable
class TranslationBackend(Protocol):
    name: str
    backend_type: str

    def is_available(self) -> bool: ...

    def translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        glossary: dict[str, str] | None = None,
    ) -> list[str | None]: ...


def build_prompt(
    texts: list[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
) -> str:
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)
    items = [{"index": i, "text": t} for i, t in enumerate(texts)]

    glossary_section = ""
    if glossary:
        keep_terms = [k for k, v in glossary.items() if k.lower() == v.lower()]
        translate_terms = [(k, v) for k, v in glossary.items() if k.lower() != v.lower()]
        parts = []
        if keep_terms:
            parts.append(f"Keep these terms as-is (DO NOT translate): {', '.join(keep_terms)}")
        if translate_terms:
            mappings = ", ".join(f"{k} → {v}" for k, v in translate_terms)
            parts.append(f"Use these translations: {mappings}")
        glossary_section = "\n\nGLOSSARY RULES:\n" + "\n".join(f"- {p}" for p in parts)

    return f"""You are a professional translator.
Translate the following text from {src_name} to {tgt_name}.
Preserve the original structure and formatting.
Input is a JSON array of indexed items.
Output ONLY a JSON array in the same order with translated text.
Do not merge or split items. Keep untranslatable terms as-is.{glossary_section}

Input:
{json.dumps(items, ensure_ascii=False)}"""


def parse_response(response: str, count: int) -> list[str | None]:
    response = response.strip()
    try:
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if fence_match:
            response = fence_match.group(1).strip()

        bracket_start = response.find("[")
        bracket_end = response.rfind("]")
        if bracket_start >= 0 and bracket_end > bracket_start:
            response = response[bracket_start:bracket_end + 1]

        data = json.loads(response)
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                result = [None] * count
                for item in data:
                    idx = item.get("index", -1)
                    text = item.get("text", "")
                    if 0 <= idx < count and text:
                        result[idx] = text
                missing = sum(1 for r in result if r is None)
                if missing:
                    logger.warning("Response missing %d/%d items", missing, count)
                return result
            result = [str(item) if item else None for item in data]
            if len(result) < count:
                logger.warning("Response has %d items, expected %d", len(result), count)
            while len(result) < count:
                result.append(None)
            return result[:count]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse response: %s", exc)

    lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
    if len(lines) >= count:
        return lines[:count]
    return lines + [None] * (count - len(lines))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_backend_protocol.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/translator/base.py tests/test_backend_protocol.py
git commit -m "feat: add TranslationBackend Protocol, build_prompt, parse_response"
```

---

## Task 3: Codex CLI backend

**Files:**
- Create: `pdf_translator/core/translator/backends/codex_cli.py`
- Test: `tests/test_backend_codex.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backend_codex.py
import json
from unittest.mock import patch, MagicMock
from pdf_translator.core.translator.backends.codex_cli import CodexCLIBackend


def test_is_available_true():
    with patch("shutil.which", return_value="/usr/bin/codex"):
        backend = CodexCLIBackend()
        assert backend.is_available() is True


def test_is_available_false():
    with patch("shutil.which", return_value=None):
        backend = CodexCLIBackend()
        assert backend.is_available() is False


def test_translate_success():
    mock_response = json.dumps([{"index": 0, "text": "안녕하세요"}])
    backend = CodexCLIBackend()
    with patch.object(backend, "_run_cli", return_value=mock_response):
        result = backend.translate(["Hello"], "en", "ko")
        assert result == ["안녕하세요"]


def test_translate_failure_returns_none():
    backend = CodexCLIBackend()
    with patch.object(backend, "_run_cli", return_value=""):
        result = backend.translate(["Hello"], "en", "ko")
        assert result == [None]


def test_name_and_type():
    backend = CodexCLIBackend()
    assert backend.name == "codex"
    assert backend.backend_type == "cli"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_backend_codex.py -v
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement codex_cli.py**

```python
# pdf_translator/core/translator/backends/codex_cli.py
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time

from pdf_translator.core.translator.base import (
    TranslationBackend,
    build_prompt,
    parse_response,
)

logger = logging.getLogger(__name__)


class CodexCLIBackend:
    name = "codex"
    backend_type = "cli"

    def __init__(self, effort: str = "low", max_retries: int = 2):
        self.effort = effort
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

    def translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        glossary: dict[str, str] | None = None,
    ) -> list[str | None]:
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._run_cli(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)

    def _run_cli(self, prompt: str) -> str:
        for attempt in range(self.max_retries + 1):
            out_path = None
            try:
                out_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, prefix="codex_out_",
                )
                out_path = out_file.name
                out_file.close()

                cmd = ["codex", "exec", "-s", "read-only", "-o", out_path]
                if self.effort:
                    cmd += ["-c", f"reasoning_effort={self.effort}"]

                proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                try:
                    proc.communicate(input=prompt, timeout=120)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    raise

                if proc.returncode == 0 and os.path.exists(out_path):
                    with open(out_path, encoding="utf-8") as f:
                        content = f.read().strip()
                    os.unlink(out_path)
                    if content:
                        return content
                else:
                    if os.path.exists(out_path):
                        os.unlink(out_path)

                if attempt < self.max_retries:
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
            except subprocess.TimeoutExpired:
                if out_path and os.path.exists(out_path):
                    os.unlink(out_path)
                logger.warning("Codex timed out (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                if attempt < self.max_retries:
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
            except OSError:
                if out_path and os.path.exists(out_path):
                    os.unlink(out_path)
                if attempt < self.max_retries:
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
        return ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_backend_codex.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/translator/backends/codex_cli.py tests/test_backend_codex.py
git commit -m "feat: extract Codex CLI into TranslationBackend"
```

---

## Task 4: Claude CLI backend

**Files:**
- Create: `pdf_translator/core/translator/backends/claude_cli.py`
- Test: `tests/test_backend_claude.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backend_claude.py
import json
from unittest.mock import patch
from pdf_translator.core.translator.backends.claude_cli import ClaudeCLIBackend


def test_is_available_true():
    with patch("shutil.which", return_value="/usr/bin/claude"):
        backend = ClaudeCLIBackend()
        assert backend.is_available() is True


def test_is_available_false():
    with patch("shutil.which", return_value=None):
        backend = ClaudeCLIBackend()
        assert backend.is_available() is False


def test_translate_success():
    mock_response = json.dumps([{"index": 0, "text": "안녕하세요"}])
    backend = ClaudeCLIBackend()
    with patch.object(backend, "_run_cli", return_value=mock_response):
        result = backend.translate(["Hello"], "en", "ko")
        assert result == ["안녕하세요"]


def test_name_and_type():
    backend = ClaudeCLIBackend()
    assert backend.name == "claude-cli"
    assert backend.backend_type == "cli"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_backend_claude.py -v
```

- [ ] **Step 3: Implement claude_cli.py**

```python
# pdf_translator/core/translator/backends/claude_cli.py
from __future__ import annotations

import logging
import shutil
import subprocess

from pdf_translator.core.translator.base import (
    build_prompt,
    parse_response,
)

logger = logging.getLogger(__name__)


class ClaudeCLIBackend:
    name = "claude-cli"
    backend_type = "cli"

    def __init__(self, model: str = "sonnet", max_retries: int = 2):
        self.model = model
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        glossary: dict[str, str] | None = None,
    ) -> list[str | None]:
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._run_cli(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)

    def _run_cli(self, prompt: str) -> str:
        for attempt in range(self.max_retries + 1):
            try:
                proc = subprocess.Popen(
                    ["claude", "--print", "--model", self.model],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                try:
                    stdout, stderr = proc.communicate(input=prompt, timeout=120)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    raise

                if proc.returncode == 0 and stdout.strip():
                    return stdout.strip()

                if attempt < self.max_retries:
                    import time
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
            except (subprocess.TimeoutExpired, OSError):
                logger.warning("Claude CLI failed (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                if attempt < self.max_retries:
                    import time
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
        return ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_backend_claude.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/translator/backends/claude_cli.py tests/test_backend_claude.py
git commit -m "feat: add Claude CLI translation backend"
```

---

## Task 5: Gemini CLI backend

**Files:**
- Create: `pdf_translator/core/translator/backends/gemini_cli.py`
- Test: `tests/test_backend_gemini.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backend_gemini.py
import json
from unittest.mock import patch
from pdf_translator.core.translator.backends.gemini_cli import GeminiCLIBackend


def test_is_available_true():
    with patch("shutil.which", return_value="/usr/bin/gemini"):
        backend = GeminiCLIBackend()
        assert backend.is_available() is True


def test_is_available_false():
    with patch("shutil.which", return_value=None):
        backend = GeminiCLIBackend()
        assert backend.is_available() is False


def test_translate_success():
    mock_response = json.dumps([{"index": 0, "text": "안녕하세요"}])
    backend = GeminiCLIBackend()
    with patch.object(backend, "_run_cli", return_value=mock_response):
        result = backend.translate(["Hello"], "en", "ko")
        assert result == ["안녕하세요"]


def test_name_and_type():
    backend = GeminiCLIBackend()
    assert backend.name == "gemini-cli"
    assert backend.backend_type == "cli"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_backend_gemini.py -v
```

- [ ] **Step 3: Implement gemini_cli.py**

```python
# pdf_translator/core/translator/backends/gemini_cli.py
from __future__ import annotations

import logging
import shutil
import subprocess

from pdf_translator.core.translator.base import (
    build_prompt,
    parse_response,
)

logger = logging.getLogger(__name__)


class GeminiCLIBackend:
    name = "gemini-cli"
    backend_type = "cli"

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        glossary: dict[str, str] | None = None,
    ) -> list[str | None]:
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._run_cli(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)

    def _run_cli(self, prompt: str) -> str:
        for attempt in range(self.max_retries + 1):
            try:
                proc = subprocess.Popen(
                    ["gemini"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                try:
                    stdout, stderr = proc.communicate(input=prompt, timeout=120)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    raise

                if proc.returncode == 0 and stdout.strip():
                    return stdout.strip()

                if attempt < self.max_retries:
                    import time
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
            except (subprocess.TimeoutExpired, OSError):
                logger.warning("Gemini CLI failed (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                if attempt < self.max_retries:
                    import time
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
        return ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_backend_gemini.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/translator/backends/gemini_cli.py tests/test_backend_gemini.py
git commit -m "feat: add Gemini CLI translation backend"
```

---

## Task 6: Google Translate backend

**Files:**
- Create: `pdf_translator/core/translator/backends/google_translate.py`
- Test: `tests/test_backend_google.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backend_google.py
from unittest.mock import patch, MagicMock
from pdf_translator.core.translator.backends.google_translate import GoogleTranslateBackend


def test_is_available_with_package():
    backend = GoogleTranslateBackend()
    with patch.dict("sys.modules", {"deep_translator": MagicMock()}):
        assert backend.is_available() is True


def test_translate_success():
    backend = GoogleTranslateBackend()
    mock_translator = MagicMock()
    mock_translator.translate.side_effect = ["안녕하세요", "세계"]
    with patch("deep_translator.GoogleTranslator", return_value=mock_translator):
        result = backend.translate(["Hello", "World"], "en", "ko")
        assert result == ["안녕하세요", "세계"]


def test_translate_partial_failure():
    backend = GoogleTranslateBackend()
    mock_translator = MagicMock()
    mock_translator.translate.side_effect = ["안녕", Exception("rate limit")]
    with patch("deep_translator.GoogleTranslator", return_value=mock_translator):
        result = backend.translate(["Hello", "World"], "en", "ko")
        assert result[0] == "안녕"
        assert result[1] is None


def test_name_and_type():
    backend = GoogleTranslateBackend()
    assert backend.name == "google-translate"
    assert backend.backend_type == "api"


def test_normalize_lang():
    backend = GoogleTranslateBackend()
    assert backend._normalize_lang("zh-CN") == "zh"
    assert backend._normalize_lang("en-US") == "en"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_backend_google.py -v
```

- [ ] **Step 3: Implement google_translate.py**

```python
# pdf_translator/core/translator/backends/google_translate.py
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_GOOGLE_LANG_MAP = {"zh": "zh-CN"}


class GoogleTranslateBackend:
    name = "google-translate"
    backend_type = "api"

    def is_available(self) -> bool:
        try:
            import deep_translator  # noqa: F401
            return True
        except ImportError:
            return False

    def translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        glossary: dict[str, str] | None = None,
    ) -> list[str | None]:
        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            return [None] * len(texts)

        src = self._normalize_lang(source_lang)
        tgt = self._normalize_lang(target_lang)
        src = _GOOGLE_LANG_MAP.get(src, src)
        tgt = _GOOGLE_LANG_MAP.get(tgt, tgt)
        translator = GoogleTranslator(source=src, target=tgt)

        results: list[str | None] = []
        for text in texts:
            if not text.strip():
                results.append(text)
                continue
            try:
                translated = translator.translate(text)
                # Apply glossary post-processing for non-LLM backend
                if glossary and translated:
                    for src_term, tgt_term in glossary.items():
                        if src_term.lower() == tgt_term.lower():
                            # keep-as-is: restore original term if it was translated
                            continue
                        # Simple replacement for explicit mappings
                        translated = translated.replace(src_term, tgt_term)
                results.append(translated)
            except Exception:
                results.append(None)
        return results

    @staticmethod
    def _normalize_lang(code: str) -> str:
        return code.strip().split("-")[0].split("_")[0].lower()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_backend_google.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/translator/backends/google_translate.py tests/test_backend_google.py
git commit -m "feat: extract Google Translate into TranslationBackend"
```

---

## Task 7: Backend Router + translate_all

**Files:**
- Create: `pdf_translator/core/translator/router.py`
- Modify: `pdf_translator/core/translator/__init__.py`, `pdf_translator/core/translator/backends/__init__.py`
- Test: `tests/test_router.py`
- Update: `tests/test_translate_all.py`, `tests/test_translator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_router.py
from unittest.mock import patch, MagicMock
from pdf_translator.core.translator.router import BackendRouter


def test_auto_select_first_available_cli():
    router = BackendRouter()
    mock_backend = MagicMock()
    mock_backend.is_available.return_value = True
    mock_backend.name = "claude-cli"
    mock_backend.backend_type = "cli"
    router._cli_backends = [mock_backend]
    router._api_backends = []

    selected = router.select("auto")
    assert selected is mock_backend


def test_auto_select_falls_through_to_api():
    router = BackendRouter()
    cli_backend = MagicMock()
    cli_backend.is_available.return_value = False
    api_backend = MagicMock()
    api_backend.is_available.return_value = True
    api_backend.name = "openai-api"
    router._cli_backends = [cli_backend]
    router._api_backends = [api_backend]
    router._fallback = None

    selected = router.select("auto")
    assert selected is api_backend


def test_explicit_select():
    router = BackendRouter()
    mock_backend = MagicMock()
    mock_backend.name = "claude-cli"
    mock_backend.is_available.return_value = True
    router._all_backends = {"claude-cli": mock_backend}

    selected = router.select("claude-cli")
    assert selected is mock_backend


def test_explicit_select_unavailable_raises():
    router = BackendRouter()
    mock_backend = MagicMock()
    mock_backend.name = "claude-cli"
    mock_backend.is_available.return_value = False
    router._all_backends = {"claude-cli": mock_backend}

    try:
        router.select("claude-cli")
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "claude-cli" in str(e)


def test_auto_select_fallback_google():
    router = BackendRouter()
    cli_backend = MagicMock()
    cli_backend.is_available.return_value = False
    fallback = MagicMock()
    fallback.is_available.return_value = True
    fallback.name = "google-translate"
    router._cli_backends = [cli_backend]
    router._api_backends = []
    router._fallback = fallback

    selected = router.select("auto")
    assert selected is fallback
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_router.py -v
```

- [ ] **Step 3: Implement router.py**

```python
# pdf_translator/core/translator/router.py
from __future__ import annotations

import logging
from pdf_translator.core.translator.backends.codex_cli import CodexCLIBackend
from pdf_translator.core.translator.backends.claude_cli import ClaudeCLIBackend
from pdf_translator.core.translator.backends.gemini_cli import GeminiCLIBackend
from pdf_translator.core.translator.backends.google_translate import GoogleTranslateBackend

logger = logging.getLogger(__name__)


class BackendRouter:
    def __init__(self, effort: str = "low"):
        codex = CodexCLIBackend(effort=effort)
        claude = ClaudeCLIBackend()
        gemini = GeminiCLIBackend()
        google = GoogleTranslateBackend()

        self._cli_backends = [codex, claude, gemini]
        self._api_backends = []  # Phase 2 will add API backends here
        self._fallback = google
        self._all_backends = {b.name: b for b in self._cli_backends + self._api_backends}
        if self._fallback:
            self._all_backends[self._fallback.name] = self._fallback

    def select(self, backend_name: str = "auto"):
        if backend_name == "auto":
            return self._auto_select()

        backend = self._all_backends.get(backend_name)
        if backend is None:
            available = ", ".join(self._all_backends.keys())
            raise RuntimeError(f"Unknown backend '{backend_name}'. Available: {available}")
        if not backend.is_available():
            raise RuntimeError(f"Backend '{backend_name}' is not available")
        return backend

    def _auto_select(self):
        for b in self._cli_backends:
            if b.is_available():
                logger.info("Auto-selected backend: %s", b.name)
                return b
        for b in self._api_backends:
            if b.is_available():
                logger.info("Auto-selected backend: %s", b.name)
                return b
        if self._fallback and self._fallback.is_available():
            logger.info("Falling back to: %s", self._fallback.name)
            return self._fallback
        raise RuntimeError("No translation backend available")

    def list_available(self) -> list[str]:
        return [b.name for b in self._all_backends.values() if b.is_available()]
```

- [ ] **Step 4: Implement backends/__init__.py registry**

```python
# pdf_translator/core/translator/backends/__init__.py
from pdf_translator.core.translator.backends.codex_cli import CodexCLIBackend
from pdf_translator.core.translator.backends.claude_cli import ClaudeCLIBackend
from pdf_translator.core.translator.backends.gemini_cli import GeminiCLIBackend
from pdf_translator.core.translator.backends.google_translate import GoogleTranslateBackend

__all__ = [
    "CodexCLIBackend",
    "ClaudeCLIBackend",
    "GeminiCLIBackend",
    "GoogleTranslateBackend",
]
```

- [ ] **Step 5: Implement core/translator/__init__.py with translate_all**

```python
# pdf_translator/core/translator/__init__.py
from __future__ import annotations

import logging
from multiprocessing import Pool

from pdf_translator.core.extractor import Element
from pdf_translator.core.translator.base import TranslationBackend, build_prompt, parse_response, LANG_NAMES
from pdf_translator.core.translator.router import BackendRouter

logger = logging.getLogger(__name__)


def detect_language(elements: list[Element]) -> str:
    from langdetect import detect, LangDetectException
    text = " ".join(el.content for el in elements if el.content.strip())[:3000]
    if not text.strip():
        return "en"
    try:
        lang = detect(text)
        return lang.split("-")[0]
    except LangDetectException:
        return "en"


def _worker_translate(
    work_item: tuple[list[dict], str, str, str, str],
) -> list[tuple[int, str, str]]:
    items, source_lang, target_lang, effort, backend_name = work_item
    uncached = [d for d in items if not d["cached"]]
    if not uncached:
        return []

    router = BackendRouter(effort=effort)
    backend = router.select(backend_name)

    texts = [d["content"] for d in uncached]
    translations = backend.translate(texts, source_lang, target_lang)
    return [
        (item["global_idx"], translated, item["content"])
        for item, translated in zip(uncached, translations)
    ]


def translate_all(
    batches: list[list[Element]],
    source_lang: str,
    target_lang: str,
    effort: str = "low",
    workers: int = 4,
    cache=None,
    backend: str = "auto",
) -> dict[int, str]:
    results: dict[int, str] = {}
    work_items = []
    global_idx = 0

    for batch in batches:
        all_cached = True
        batch_items = []
        for el in batch:
            cached_text = cache.get(el.content, source_lang, target_lang) if cache else None
            if cached_text is not None:
                results[global_idx] = cached_text
            else:
                all_cached = False
            batch_items.append({
                "type": el.type, "content": el.content,
                "page_number": el.page_number, "bbox": el.bbox,
                "global_idx": global_idx,
                "cached": cached_text is not None,
            })
            global_idx += 1
        if not all_cached:
            work_items.append((batch_items, source_lang, target_lang, effort, backend))

    if not work_items:
        return results

    workers = max(1, workers)
    with Pool(processes=min(workers, len(work_items))) as pool:
        for batch_results in pool.map(_worker_translate, work_items):
            for gidx, translated, original in batch_results:
                if translated is not None:
                    results[gidx] = translated
                    if cache:
                        cache.put(original, source_lang, target_lang, translated)
                elif gidx not in results:
                    results[gidx] = original

    return results
```

- [ ] **Step 6: Update test_translate_all.py and test_translator.py imports**

Update `tests/test_translate_all.py`:
```python
# Change import
from pdf_translator.core.extractor import Element
from pdf_translator.core.cache import TranslationCache
from pdf_translator.core.translator import translate_all
```

Update `_mock_worker` signature to match new 5-tuple:
```python
def _mock_worker(work_item):
    items, src, tgt, effort, backend_name = work_item
    return [
        (item["global_idx"], f"[{tgt}]{item['content']}", item["content"])
        for item in items
        if not item["cached"]
    ]
```

Update `tests/test_translator.py` to import from new locations:
```python
from pdf_translator.core.translator.base import build_prompt, parse_response
from pdf_translator.core.translator import detect_language
from pdf_translator.core.translator.backends.codex_cli import CodexCLIBackend
from pdf_translator.core.translator.backends.google_translate import GoogleTranslateBackend
```

Rewrite tests that reference old functions to use new backend classes.

- [ ] **Step 7: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add BackendRouter with auto-select, rewrite translate_all"
```

---

## Task 8: PDF Builder v2 — redaction + font measurement

**Files:**
- Modify: `pdf_translator/core/pdf_builder.py`
- Test: `tests/test_pdf_builder_v2.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pdf_builder_v2.py
import tempfile
from pathlib import Path
import fitz
from pdf_translator.core.extractor import Element
from pdf_translator.core.pdf_builder import build_pdf, _sample_background_color, _fit_fontsize_v2


def _create_test_pdf(path: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Hello World", fontsize=14, color=(0, 0, 0))
    page.insert_text((72, 140), "Test paragraph with some text.", fontsize=12, color=(0.2, 0.2, 0.8))
    doc.save(path)
    doc.close()


def test_build_pdf_creates_output():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "src.pdf")
        dst = str(Path(d) / "dst.pdf")
        _create_test_pdf(src)
        elements = [
            Element(type="heading", content="Hello World", page_number=1,
                    bbox=[72, 90, 200, 110], font_size=14.0, text_color=[0, 0, 0]),
        ]
        build_pdf(src, dst, elements, {0: "안녕 세계"})
        assert Path(dst).exists()
        doc = fitz.open(dst)
        assert len(doc) >= 1
        doc.close()


def test_build_pdf_preserves_pages():
    with tempfile.TemporaryDirectory() as d:
        src = str(Path(d) / "src.pdf")
        dst = str(Path(d) / "dst.pdf")
        doc = fitz.open()
        doc.new_page()
        doc.new_page()
        doc.save(src)
        doc.close()

        build_pdf(src, dst, [], {})
        out = fitz.open(dst)
        assert len(out) == 2
        out.close()


def test_fit_fontsize_v2_respects_height():
    rect = fitz.Rect(0, 0, 100, 20)
    # A very long text should get a small font to fit height
    long_text = "A" * 200
    size = _fit_fontsize_v2(long_text, rect, 14.0)
    assert size <= 14.0
    assert size >= 4.0


def test_sample_background_color_white():
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(10, 10, 50, 50)
    pixmap = page.get_pixmap(clip=rect)
    color = _sample_background_color(pixmap)
    # White page → (1.0, 1.0, 1.0) approximately
    assert all(c > 0.95 for c in color)
    doc.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_pdf_builder_v2.py -v
```

Expected: FAIL (functions not found or signature mismatch).

- [ ] **Step 3: Rewrite pdf_builder.py**

```python
# pdf_translator/core/pdf_builder.py
from __future__ import annotations

import logging
import math
from pathlib import Path

import fitz

from pdf_translator.core.extractor import Element

logger = logging.getLogger(__name__)

CJK_FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/baekmuk/batang.ttf",
    "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]


def _find_cjk_font() -> str | None:
    for p in CJK_FONT_PATHS:
        if Path(p).exists():
            return p
    return None


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
            0xAC00 <= cp <= 0xD7AF or 0x3040 <= cp <= 0x30FF)


def _builtin_cjk_fontname(text: str) -> str:
    for ch in text:
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7AF:
            return "korea"
        if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF:
            return "japan"
    return "china-ss"


def _sample_background_color(pixmap: fitz.Pixmap) -> tuple[float, float, float]:
    """Sample average color from a pixmap region. Returns (r, g, b) in 0-1 range."""
    samples = pixmap.samples
    n = pixmap.n  # components per pixel (3=RGB, 4=RGBA)
    pixel_count = pixmap.width * pixmap.height
    if pixel_count == 0:
        return (1.0, 1.0, 1.0)

    r_sum = g_sum = b_sum = 0
    for i in range(0, len(samples), n):
        r_sum += samples[i]
        g_sum += samples[i + 1]
        b_sum += samples[i + 2]

    return (
        r_sum / (pixel_count * 255),
        g_sum / (pixel_count * 255),
        b_sum / (pixel_count * 255),
    )


def _fit_fontsize_v2(text: str, rect: fitz.Rect, max_size: float) -> float:
    """Binary search for font size that fits text within rect, considering height."""
    lo, hi = 4.0, max_size
    for _ in range(12):
        mid = (lo + hi) / 2
        estimated_width = sum(mid * (1.0 if _is_cjk(ch) else 0.6) for ch in text)
        num_lines = math.ceil(estimated_width / rect.width) if rect.width > 0 else 1
        estimated_height = num_lines * mid * 1.2
        fits_width = estimated_width <= rect.width or num_lines > 1
        fits_height = estimated_height <= rect.height
        if fits_width and fits_height:
            lo = mid
        else:
            hi = mid
    return lo


def _build_html(text: str, fontsize: float, text_color: list[int], cjk_font: str | None) -> str:
    """Build HTML string with CSS styling for insert_htmlbox."""
    r = text_color[0] if text_color else 0
    g = text_color[1] if len(text_color) > 1 else 0
    b = text_color[2] if len(text_color) > 2 else 0
    font_family = "sans-serif"
    if cjk_font:
        font_family = f"CJK, {font_family}"
    elif any(_is_cjk(ch) for ch in text):
        font_family = f"{_builtin_cjk_fontname(text)}, {font_family}"
    return (
        f'<span style="font-size:{fontsize:.1f}px; '
        f'color:rgb({r},{g},{b}); '
        f'font-family:{font_family};">'
        f'{text}</span>'
    )


def build_pdf(
    src_path: str,
    dst_path: str,
    elements: list[Element],
    translations: dict[int, str],
    is_scanned: bool = False,
) -> None:
    doc = fitz.open(src_path)
    try:
        cjk_font = _find_cjk_font()

        by_page: dict[int, list[tuple[int, Element]]] = {}
        for idx, el in enumerate(elements):
            if idx in translations:
                by_page.setdefault(el.page_number, []).append((idx, el))

        for page_num, items in by_page.items():
            if page_num < 1 or page_num > len(doc):
                continue
            page = doc[page_num - 1]
            page_height = page.rect.height

            if is_scanned:
                # Scanned PDF: cover with background color
                for idx, el in items:
                    bbox = el.bbox
                    if len(bbox) != 4:
                        continue
                    x0, y_bottom, x1, y_top = bbox
                    rect = fitz.Rect(x0, page_height - y_top, x1, page_height - y_bottom)

                    pixmap = page.get_pixmap(clip=rect)
                    bg_color = _sample_background_color(pixmap)

                    shape = page.new_shape()
                    shape.draw_rect(rect)
                    shape.finish(fill=bg_color)
                    shape.commit()
            else:
                # Text PDF: use redaction API to remove text only
                for idx, el in items:
                    bbox = el.bbox
                    if len(bbox) != 4:
                        continue
                    x0, y_bottom, x1, y_top = bbox
                    rect = fitz.Rect(x0, page_height - y_top, x1, page_height - y_bottom)
                    page.add_redact_annot(rect, fill=(1, 1, 1))

                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            # Insert translated text
            for idx, el in items:
                bbox = el.bbox
                if len(bbox) != 4:
                    continue
                x0, y_bottom, x1, y_top = bbox
                rect = fitz.Rect(x0, page_height - y_top, x1, page_height - y_bottom)

                translated = translations[idx]
                fontsize = _fit_fontsize_v2(translated, rect, el.font_size)

                # Try insert_htmlbox first (CSS styling + auto-wrap)
                inserted = False
                try:
                    html = _build_html(translated, fontsize, el.text_color, cjk_font)
                    rc = page.insert_htmlbox(rect, html)
                    if rc >= 0:
                        inserted = True
                except Exception:
                    pass

                # Fallback to insert_textbox
                if not inserted:
                    try:
                        kwargs = {"fontsize": fontsize}
                        if cjk_font:
                            kwargs["fontfile"] = cjk_font
                            kwargs["fontname"] = "CJK"
                        elif any(_is_cjk(ch) for ch in translated):
                            kwargs["fontname"] = _builtin_cjk_fontname(translated)
                        color_floats = tuple(c / 255 for c in el.text_color[:3]) if el.text_color else (0, 0, 0)
                        kwargs["color"] = color_floats
                        rc = page.insert_textbox(rect, translated, **kwargs)
                        if rc >= 0:
                            inserted = True
                    except Exception:
                        pass

                # Last resort: insert_text at top-left
                if not inserted:
                    try:
                        page.insert_text(
                            rect.tl + fitz.Point(0, fontsize),
                            translated, fontsize=fontsize,
                        )
                    except Exception:
                        logger.warning("Failed to insert text at page %d, idx %d", page_num, idx)

        doc.save(dst_path)
    finally:
        doc.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_pdf_builder_v2.py tests/test_pdf_builder.py -v
```

Expected: All tests PASS (both new and existing).

- [ ] **Step 5: Commit**

```bash
git add pdf_translator/core/pdf_builder.py tests/test_pdf_builder_v2.py
git commit -m "feat: rewrite pdf_builder with redaction API + insert_htmlbox"
```

---

## Task 9: CLI migration + pyproject.toml

**Files:**
- Create: `pdf_translator/cli/main.py`
- Delete: `pdf_translator/cli.py`
- Modify: `pdf_translator/__init__.py`, `pyproject.toml`
- Update: `tests/test_cli.py`, `tests/test_integration.py`

- [ ] **Step 1: Create cli/main.py from existing cli.py**

```python
# pdf_translator/cli/main.py
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from pdf_translator.core.config import TranslatorConfig
from pdf_translator.core.extractor import extract_pdf
from pdf_translator.core.chunker import build_batches
from pdf_translator.core.cache import TranslationCache
from pdf_translator.core.translator import translate_all, detect_language
from pdf_translator.core.translator.base import LANG_NAMES
from pdf_translator.core.translator.router import BackendRouter
from pdf_translator.core.pdf_builder import build_pdf
from pdf_translator.core.md_builder import build_markdown

console = Console()


def parse_args(argv: list[str] | None = None) -> TranslatorConfig:
    parser = argparse.ArgumentParser(
        prog="pdf-translator",
        description="Translate PDF documents with pluggable LLM backends",
    )
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    default_workers = min(os.cpu_count() or 4, 8)
    parser.add_argument("--workers", type=int, default=default_workers, help="Parallel processes")
    parser.add_argument("--source-lang", default="auto", help="Source language (auto: detect)")
    parser.add_argument("--target-lang", default="ko", help="Target language code")
    parser.add_argument("--effort", default="low", help="Codex reasoning effort")
    parser.add_argument("--pages", default=None, help="Pages to process (e.g. 1,3,5-7)")
    parser.add_argument("--no-cache", action="store_true", help="Disable translation cache")
    parser.add_argument("--backend", default="auto", help="Translation backend (auto, codex, claude-cli, gemini-cli, google-translate)")

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
        backend=args.backend,
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
        task = progress.add_task("Extracting PDF...", total=4)
        elements = extract_pdf(str(input_path), output_dir=str(output_dir), pages=cfg.pages)
        console.print(f"  Extracted [cyan]{len(elements)}[/cyan] text elements")

        if cfg.source_lang == "auto":
            cfg.source_lang = detect_language(elements)
            lang_label = LANG_NAMES.get(cfg.source_lang, cfg.source_lang)
            console.print(f"  Detected language: [cyan]{lang_label}[/cyan]")

        router = BackendRouter(effort=cfg.effort)
        backend_obj = router.select(cfg.backend)
        console.print(f"  Backend: [cyan]{backend_obj.name}[/cyan]")
        progress.update(task, advance=1)

        progress.update(task, description="Building batches...")
        valid_indices = [i for i, el in enumerate(elements) if el.content.strip()]
        batches = build_batches(elements)
        console.print(f"  Created [cyan]{len(batches)}[/cyan] translation batches")
        progress.update(task, advance=1)

        progress.update(task, description=f"Translating ({cfg.workers} workers)...")
        workers = max(1, cfg.workers)
        cache = TranslationCache(output_dir / "cache.db") if cfg.use_cache else None
        try:
            raw_translations = translate_all(
                batches,
                source_lang=cfg.source_lang,
                target_lang=cfg.target_lang,
                effort=cfg.effort,
                workers=workers,
                cache=cache,
                backend=cfg.backend,
            )
            translations = {
                valid_indices[gi]: text
                for gi, text in raw_translations.items()
                if gi < len(valid_indices)
            }
            console.print(f"  Translated [cyan]{len(translations)}[/cyan] segments")
            progress.update(task, advance=1)

            progress.update(task, description="Generating output...")
            pdf_out = str(output_dir / f"{stem}_translated.pdf")
            build_pdf(str(input_path), pdf_out, elements, translations)
            console.print(f"  PDF: [green]{pdf_out}[/green]")

            md_out = output_dir / f"{stem}_translated.md"
            md_content = build_markdown(elements, translations)
            md_out.write_text(md_content, encoding="utf-8")
            console.print(f"  Markdown: [green]{md_out}[/green]")

            progress.update(task, advance=1)
        finally:
            if cache:
                cache.flush()
                cache.close()

    console.print("[bold green]Done![/bold green]")


def main():
    cfg = parse_args()
    run(cfg)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add `backend` field to TranslatorConfig**

In `pdf_translator/core/config.py`, add:
```python
backend: str = "auto"
```

- [ ] **Step 3: Delete old cli.py and translator.py**

```bash
git rm pdf_translator/cli.py
git rm pdf_translator/translator.py
```

- [ ] **Step 4: Update pyproject.toml entry point**

```toml
[project.scripts]
pdf-translator = "pdf_translator.cli.main:main"
```

- [ ] **Step 5: Update test_cli.py imports**

```python
# Change:
from pdf_translator.cli import parse_args
# To:
from pdf_translator.cli.main import parse_args
```

- [ ] **Step 6: Update test_integration.py imports**

```python
# Change:
from pdf_translator.cli import run
from pdf_translator.config import TranslatorConfig
# To:
from pdf_translator.cli.main import run
from pdf_translator.core.config import TranslatorConfig
```

Also update mock patches to new paths:
```python
with patch("pdf_translator.cli.main.extract_pdf", return_value=mock_elements), \
     patch("pdf_translator.core.translator.backends.codex_cli.CodexCLIBackend._run_cli",
           side_effect=mock_run_codex), \
     patch("pdf_translator.core.translator.Pool", _InProcessPool):
```

- [ ] **Step 7: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: migrate CLI to new core/ structure, add --backend flag"
```

---

## Task 10: Core public API + final cleanup

**Files:**
- Modify: `pdf_translator/core/__init__.py`
- Create: `tests/test_public_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_public_api.py
"""Verify the public Python API is importable and works."""

def test_core_imports():
    from pdf_translator.core import translate_pdf
    assert callable(translate_pdf)


def test_translate_pdf_with_mock(tmp_path):
    import fitz
    from unittest.mock import patch, MagicMock
    from pdf_translator.core import translate_pdf

    # Create a minimal test PDF
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Hello", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    mock_elements = []
    with patch("pdf_translator.core.extract_pdf", return_value=mock_elements):
        result = translate_pdf(str(pdf_path), target_lang="ko", output_dir=str(tmp_path))
        assert result is not None
        assert "pdf_path" in result
        assert "md_path" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_public_api.py -v
```

- [ ] **Step 3: Implement core/__init__.py public API**

```python
# pdf_translator/core/__init__.py
"""PDF Translator core library — public API."""
from __future__ import annotations

from pathlib import Path

from pdf_translator.core.config import TranslatorConfig
from pdf_translator.core.extractor import Element, extract_pdf
from pdf_translator.core.chunker import build_batches
from pdf_translator.core.cache import TranslationCache
from pdf_translator.core.translator import translate_all, detect_language
from pdf_translator.core.translator.router import BackendRouter
from pdf_translator.core.pdf_builder import build_pdf
from pdf_translator.core.md_builder import build_markdown


def translate_pdf(
    input_path: str,
    target_lang: str = "ko",
    source_lang: str = "auto",
    backend: str = "auto",
    effort: str = "low",
    workers: int = 4,
    output_dir: str = "./output",
    use_cache: bool = True,
    pages: str | None = None,
    glossary: str | dict | None = None,
) -> dict:
    """Translate a PDF file. Returns dict with output paths.

    Args:
        input_path: Path to input PDF.
        target_lang: Target language code.
        source_lang: Source language code or "auto".
        backend: Backend name or "auto".
        effort: Codex reasoning effort.
        workers: Number of parallel workers.
        output_dir: Output directory.
        use_cache: Enable SQLite translation cache.
        pages: Pages to process (e.g. "1,3,5-7").
        glossary: Path to glossary CSV or dict.
    """
    input_p = Path(input_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_p.stem

    elements = extract_pdf(str(input_p), output_dir=str(out_dir), pages=pages)

    if source_lang == "auto" and elements:
        source_lang = detect_language(elements)

    valid_indices = [i for i, el in enumerate(elements) if el.content.strip()]
    batches = build_batches(elements)

    cache = TranslationCache(out_dir / "cache.db") if use_cache else None
    try:
        raw = translate_all(
            batches, source_lang=source_lang, target_lang=target_lang,
            effort=effort, workers=workers, cache=cache, backend=backend,
        )
        translations = {
            valid_indices[gi]: text
            for gi, text in raw.items()
            if gi < len(valid_indices)
        }
    finally:
        if cache:
            cache.flush()
            cache.close()

    pdf_out = str(out_dir / f"{stem}_translated.pdf")
    build_pdf(str(input_p), pdf_out, elements, translations)

    md_out = out_dir / f"{stem}_translated.md"
    md_content = build_markdown(elements, translations)
    md_out.write_text(md_content, encoding="utf-8")

    return {
        "pdf_path": pdf_out,
        "md_path": str(md_out),
        "segments_total": len(elements),
        "segments_translated": len(translations),
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_public_api.py -v
```

Expected: All PASS.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add translate_pdf() public Python API"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Core scaffolding + module migration | `core/`, all existing modules |
| 2 | TranslationBackend Protocol + prompt/parse | `core/translator/base.py` |
| 3 | Codex CLI backend | `core/translator/backends/codex_cli.py` |
| 4 | Claude CLI backend | `core/translator/backends/claude_cli.py` |
| 5 | Gemini CLI backend | `core/translator/backends/gemini_cli.py` |
| 6 | Google Translate backend | `core/translator/backends/google_translate.py` |
| 7 | Backend Router + translate_all | `core/translator/router.py` |
| 8 | PDF Builder v2 (redaction + htmlbox) | `core/pdf_builder.py` |
| 9 | CLI migration + pyproject.toml | `cli/main.py` |
| 10 | Public Python API | `core/__init__.py` |

**After Phase 1 completion:**
- `pdf-translator paper.pdf` works with improved layout
- `pdf-translator paper.pdf --backend claude-cli` uses Claude CLI
- `from pdf_translator.core import translate_pdf` works as library
- All existing tests pass + new backend/builder tests

**Next plans:** Phase 2 (glossary + draft + API backends), Phase 3 (OCR), Phase 4 (web UI).
