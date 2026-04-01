# Phase 2: Core Features — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add glossary system (3-tier with built-in packs), draft/review mode (JSON export/import/retranslate), and API backends (OpenAI, Anthropic, Google, OpenRouter) to complete the professional translation feature set.

**Architecture:** Glossary integrates into the translation pipeline via prompt injection (LLM) and post-processing (Google Translate). Draft is a JSON intermediate format enabling review/edit before final PDF build. API backends follow the same `TranslationBackend` Protocol from Phase 1.

**Tech Stack:** Python 3.10+, existing core/ architecture from Phase 1, openai/anthropic/google-generativeai/requests SDKs

**Spec:** `docs/superpowers/specs/2026-04-01-pdf-translator-v2-design.md` §5, §7, §4.2

**Prerequisites:** Phase 1 complete (core/ structure, TranslationBackend Protocol, BackendRouter).

---

## File Map

### New files to create

| File | Responsibility |
|------|----------------|
| `pdf_translator/core/glossary.py` | Glossary loading, merging, 3-tier priority |
| `pdf_translator/core/draft.py` | Draft JSON load/save/build |
| `pdf_translator/core/translator/backends/openai_api.py` | OpenAI API backend |
| `pdf_translator/core/translator/backends/anthropic_api.py` | Anthropic API backend |
| `pdf_translator/core/translator/backends/google_api.py` | Google Gemini API backend |
| `pdf_translator/core/translator/backends/openrouter_api.py` | OpenRouter API backend |
| `pdf_translator/data/glossaries/cs-general.csv` | Built-in CS glossary |
| `pdf_translator/data/glossaries/ml-ai.csv` | Built-in ML/AI glossary |
| `tests/test_glossary.py` | Glossary tests |
| `tests/test_draft.py` | Draft tests |
| `tests/test_backend_openai.py` | OpenAI backend tests |
| `tests/test_backend_anthropic.py` | Anthropic backend tests |
| `tests/test_backend_google_api.py` | Google API backend tests |
| `tests/test_backend_openrouter.py` | OpenRouter backend tests |

### Files to modify

| File | Changes |
|------|---------|
| `pdf_translator/core/translator/base.py` | `build_prompt()` already supports glossary — no change needed |
| `pdf_translator/core/translator/router.py` | Register API backends |
| `pdf_translator/core/translator/backends/__init__.py` | Export new backends |
| `pdf_translator/core/config.py` | Add `glossary`, `draft_only`, `build_from` fields |
| `pdf_translator/cli/main.py` | Add `--glossary`, `--draft-only`, `--build-from`, `--retranslate` flags |
| `pdf_translator/core/__init__.py` | Pass glossary to translate_pdf() |
| `pyproject.toml` | Add optional deps `[api]` |

---

## Task 1: Glossary System

**Files:**
- Create: `pdf_translator/core/glossary.py`, `pdf_translator/data/glossaries/cs-general.csv`, `pdf_translator/data/glossaries/ml-ai.csv`
- Test: `tests/test_glossary.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_glossary.py
import tempfile
from pathlib import Path
from pdf_translator.core.glossary import Glossary


def test_load_csv_2col():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("source,target\ntransformer,트랜스포머\nattention,어텐션\n")
        f.flush()
        g = Glossary.from_csv(f.name)
    assert g.get("transformer") == "트랜스포머"
    assert g.get("attention") == "어텐션"


def test_load_csv_3col_keep():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("source,target,rule\nAPI,API,keep\nmethod,방법,translate\n")
        f.flush()
        g = Glossary.from_csv(f.name)
    assert g.get("API") == "API"
    assert g.get("method") == "방법"
    assert g.keep_terms == ["API"]


def test_load_dict():
    g = Glossary.from_dict({"transformer": "트랜스포머", "GPU": "GPU"})
    assert g.get("transformer") == "트랜스포머"
    assert "GPU" in g.keep_terms


def test_merge_priority():
    """User glossary overrides built-in."""
    builtin = Glossary.from_dict({"API": "API", "transformer": "transformer"})
    user = Glossary.from_dict({"transformer": "트랜스포머"})
    merged = Glossary.merge(builtin, user)
    assert merged.get("transformer") == "트랜스포머"  # user wins
    assert merged.get("API") == "API"  # builtin preserved


def test_to_prompt_dict():
    g = Glossary.from_dict({"API": "API", "method": "방법"})
    d = g.to_prompt_dict()
    assert d["API"] == "API"
    assert d["method"] == "방법"


def test_builtin_packs_exist():
    from pdf_translator.core.glossary import load_builtin_pack
    cs = load_builtin_pack("cs-general")
    assert cs is not None
    assert "API" in cs.to_prompt_dict()


def test_load_unknown_pack_returns_none():
    from pdf_translator.core.glossary import load_builtin_pack
    assert load_builtin_pack("nonexistent") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_glossary.py -v`

- [ ] **Step 3: Create built-in glossary CSV files**

```bash
mkdir -p pdf_translator/data/glossaries
```

`pdf_translator/data/glossaries/cs-general.csv`:
```csv
source,target,rule
API,API,keep
GPU,GPU,keep
CPU,CPU,keep
SDK,SDK,keep
HTTP,HTTP,keep
HTTPS,HTTPS,keep
REST,REST,keep
JSON,JSON,keep
XML,XML,keep
SQL,SQL,keep
URL,URL,keep
CSS,CSS,keep
HTML,HTML,keep
TCP,TCP,keep
UDP,UDP,keep
IP,IP,keep
DNS,DNS,keep
SSH,SSH,keep
SSL,SSL,keep
TLS,TLS,keep
OAuth,OAuth,keep
JWT,JWT,keep
CORS,CORS,keep
CI/CD,CI/CD,keep
DevOps,DevOps,keep
Docker,Docker,keep
Kubernetes,Kubernetes,keep
Linux,Linux,keep
Git,Git,keep
GitHub,GitHub,keep
```

`pdf_translator/data/glossaries/ml-ai.csv`:
```csv
source,target,rule
BERT,BERT,keep
GPT,GPT,keep
LSTM,LSTM,keep
GAN,GAN,keep
CNN,CNN,keep
RNN,RNN,keep
ResNet,ResNet,keep
ImageNet,ImageNet,keep
PyTorch,PyTorch,keep
TensorFlow,TensorFlow,keep
Adam,Adam,keep
SGD,SGD,keep
ReLU,ReLU,keep
softmax,softmax,keep
dropout,dropout,keep
fine-tuning,파인튜닝,translate
transformer,transformer,keep
attention mechanism,어텐션 메커니즘,translate
backpropagation,역전파,translate
epoch,에폭,translate
batch size,배치 크기,translate
learning rate,학습률,translate
overfitting,과적합,translate
underfitting,과소적합,translate
embedding,임베딩,translate
tokenizer,토크나이저,translate
inference,추론,translate
pre-training,사전 학습,translate
```

- [ ] **Step 4: Implement glossary.py**

```python
# pdf_translator/core/glossary.py
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data" / "glossaries"


@dataclass
class Glossary:
    entries: dict[str, str] = field(default_factory=dict)
    keep_terms: list[str] = field(default_factory=list)

    def get(self, term: str) -> str | None:
        return self.entries.get(term)

    def to_prompt_dict(self) -> dict[str, str]:
        return dict(self.entries)

    @classmethod
    def from_csv(cls, path: str | Path) -> Glossary:
        entries = {}
        keep_terms = []
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                source = row.get("source", "").strip()
                target = row.get("target", "").strip()
                rule = row.get("rule", "").strip().lower()
                if not source:
                    continue
                entries[source] = target or source
                if rule == "keep" or (not rule and source.lower() == target.lower()):
                    keep_terms.append(source)
        return cls(entries=entries, keep_terms=keep_terms)

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> Glossary:
        keep_terms = [k for k, v in d.items() if k.lower() == v.lower()]
        return cls(entries=dict(d), keep_terms=keep_terms)

    @classmethod
    def merge(cls, *glossaries: Glossary) -> Glossary:
        """Merge glossaries. Later ones override earlier ones."""
        merged_entries = {}
        merged_keep = []
        for g in glossaries:
            merged_entries.update(g.entries)
            for k in g.keep_terms:
                if k not in merged_keep:
                    merged_keep.append(k)
        # Re-evaluate keep based on final merged state
        final_keep = [k for k in merged_keep if merged_entries.get(k, "").lower() == k.lower()]
        return cls(entries=merged_entries, keep_terms=final_keep)


def load_builtin_pack(name: str) -> Glossary | None:
    path = _DATA_DIR / f"{name}.csv"
    if not path.exists():
        return None
    return Glossary.from_csv(path)


def load_glossary(source: str | dict | Path | None) -> Glossary | None:
    """Load glossary from various sources."""
    if source is None:
        return None
    if isinstance(source, dict):
        return Glossary.from_dict(source)
    path = Path(source)
    if path.exists():
        return Glossary.from_csv(path)
    # Try as builtin pack name
    return load_builtin_pack(str(source))
```

- [ ] **Step 5: Run tests, verify pass**

Run: `python -m pytest tests/test_glossary.py -v`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add glossary system with 3-tier priority and built-in packs"
```

---

## Task 2: Draft System

**Files:**
- Create: `pdf_translator/core/draft.py`
- Test: `tests/test_draft.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_draft.py
import json
import tempfile
from pathlib import Path
from pdf_translator.core.draft import Draft, DraftElement


def test_create_draft():
    elements = [
        DraftElement(index=0, type="heading", original="Hello", translated="안녕",
                     page=1, bbox=[0, 0, 100, 20]),
        DraftElement(index=1, type="paragraph", original="World", translated="세계",
                     page=1, bbox=[0, 20, 100, 40]),
    ]
    draft = Draft(
        source_file="test.pdf", source_lang="en", target_lang="ko",
        backend="claude-cli", elements=elements,
    )
    assert len(draft.elements) == 2
    assert draft.elements[0].status == "accepted"


def test_draft_save_load(tmp_path):
    draft = Draft(
        source_file="test.pdf", source_lang="en", target_lang="ko",
        backend="codex", elements=[
            DraftElement(index=0, type="heading", original="Hi", translated="안녕",
                         page=1, bbox=[0, 0, 100, 20]),
        ],
    )
    path = tmp_path / "draft.json"
    draft.save(str(path))
    loaded = Draft.load(str(path))
    assert loaded.source_file == "test.pdf"
    assert loaded.elements[0].translated == "안녕"


def test_draft_modify_element():
    draft = Draft(
        source_file="test.pdf", source_lang="en", target_lang="ko",
        backend="codex", elements=[
            DraftElement(index=0, type="paragraph", original="Hello", translated="안녕",
                         page=1, bbox=[0, 0, 100, 20]),
        ],
    )
    draft.elements[0].user_edit = "안녕하세요"
    draft.elements[0].status = "modified"
    assert draft.elements[0].effective_translation == "안녕하세요"


def test_draft_effective_translation_default():
    el = DraftElement(index=0, type="paragraph", original="Hello", translated="안녕",
                      page=1, bbox=[0, 0, 100, 20])
    assert el.effective_translation == "안녕"


def test_draft_to_translations():
    draft = Draft(
        source_file="test.pdf", source_lang="en", target_lang="ko",
        backend="codex", elements=[
            DraftElement(index=0, type="heading", original="Hi", translated="안녕",
                         page=1, bbox=[0, 0, 100, 20]),
            DraftElement(index=1, type="paragraph", original="World", translated="세계",
                         page=1, bbox=[0, 20, 100, 40], user_edit="세상", status="modified"),
        ],
    )
    translations = draft.to_translations()
    assert translations[0] == "안녕"
    assert translations[1] == "세상"  # user_edit takes precedence


def test_draft_pending_indices():
    draft = Draft(
        source_file="test.pdf", source_lang="en", target_lang="ko",
        backend="codex", elements=[
            DraftElement(index=0, type="heading", original="Hi", translated="안녕",
                         page=1, bbox=[0, 0, 100, 20], status="accepted"),
            DraftElement(index=1, type="paragraph", original="World", translated=None,
                         page=1, bbox=[0, 20, 100, 40], status="pending"),
        ],
    )
    pending = draft.pending_indices()
    assert pending == [1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_draft.py -v`

- [ ] **Step 3: Implement draft.py**

```python
# pdf_translator/core/draft.py
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DraftElement:
    index: int
    type: str
    original: str
    translated: str | None
    page: int
    bbox: list[float]
    status: str = "accepted"  # accepted | modified | rejected | pending
    confidence: float | None = None
    user_edit: str | None = None

    @property
    def effective_translation(self) -> str | None:
        if self.user_edit is not None:
            return self.user_edit
        return self.translated


@dataclass
class Draft:
    source_file: str
    source_lang: str
    target_lang: str
    backend: str
    elements: list[DraftElement]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    glossary_applied: list[str] = field(default_factory=list)

    def save(self, path: str | Path) -> None:
        data = {
            "source_file": self.source_file,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "backend": self.backend,
            "created_at": self.created_at,
            "glossary_applied": self.glossary_applied,
            "elements": [asdict(el) for el in self.elements],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Draft:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        elements = [DraftElement(**el) for el in data["elements"]]
        return cls(
            source_file=data["source_file"],
            source_lang=data["source_lang"],
            target_lang=data["target_lang"],
            backend=data["backend"],
            elements=elements,
            created_at=data.get("created_at", ""),
            glossary_applied=data.get("glossary_applied", []),
        )

    def to_translations(self) -> dict[int, str]:
        result = {}
        for el in self.elements:
            text = el.effective_translation
            if text is not None:
                result[el.index] = text
        return result

    def pending_indices(self) -> list[int]:
        return [el.index for el in self.elements if el.status == "pending" or el.translated is None]
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python -m pytest tests/test_draft.py -v`

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Draft system for translation review/edit"
```

---

## Task 3: API Backends (OpenAI, Anthropic, Google, OpenRouter)

**Files:**
- Create: `pdf_translator/core/translator/backends/openai_api.py`, `anthropic_api.py`, `google_api.py`, `openrouter_api.py`
- Test: `tests/test_backend_openai.py`, `test_backend_anthropic.py`, `test_backend_google_api.py`, `test_backend_openrouter.py`

All 4 API backends follow the same pattern:
1. Check for API key in environment variable
2. Build prompt using `build_prompt()` from base.py
3. Call the API via SDK or HTTP
4. Parse response using `parse_response()` from base.py

- [ ] **Step 1: Write failing tests for all 4 backends**

```python
# tests/test_backend_openai.py
import json, os
from unittest.mock import patch, MagicMock
from pdf_translator.core.translator.backends.openai_api import OpenAIBackend

def test_is_available_with_key():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
        assert OpenAIBackend().is_available() is True

def test_is_available_without_key():
    with patch.dict(os.environ, {}, clear=True):
        assert OpenAIBackend().is_available() is False

def test_translate_success():
    backend = OpenAIBackend()
    mock_response = json.dumps([{"index": 0, "text": "안녕"}])
    with patch.object(backend, "_call_api", return_value=mock_response):
        result = backend.translate(["Hello"], "en", "ko")
        assert result == ["안녕"]

def test_name_and_type():
    b = OpenAIBackend()
    assert b.name == "openai-api"
    assert b.backend_type == "api"
```

```python
# tests/test_backend_anthropic.py
import json, os
from unittest.mock import patch
from pdf_translator.core.translator.backends.anthropic_api import AnthropicBackend

def test_is_available_with_key():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        assert AnthropicBackend().is_available() is True

def test_is_available_without_key():
    with patch.dict(os.environ, {}, clear=True):
        assert AnthropicBackend().is_available() is False

def test_translate_success():
    backend = AnthropicBackend()
    mock_response = json.dumps([{"index": 0, "text": "안녕"}])
    with patch.object(backend, "_call_api", return_value=mock_response):
        result = backend.translate(["Hello"], "en", "ko")
        assert result == ["안녕"]

def test_name_and_type():
    b = AnthropicBackend()
    assert b.name == "anthropic-api"
    assert b.backend_type == "api"
```

```python
# tests/test_backend_google_api.py
import json, os
from unittest.mock import patch
from pdf_translator.core.translator.backends.google_api import GoogleAPIBackend

def test_is_available_with_key():
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
        assert GoogleAPIBackend().is_available() is True

def test_is_available_without_key():
    with patch.dict(os.environ, {}, clear=True):
        assert GoogleAPIBackend().is_available() is False

def test_translate_success():
    backend = GoogleAPIBackend()
    mock_response = json.dumps([{"index": 0, "text": "안녕"}])
    with patch.object(backend, "_call_api", return_value=mock_response):
        result = backend.translate(["Hello"], "en", "ko")
        assert result == ["안녕"]

def test_name_and_type():
    b = GoogleAPIBackend()
    assert b.name == "google-api"
    assert b.backend_type == "api"
```

```python
# tests/test_backend_openrouter.py
import json, os
from unittest.mock import patch
from pdf_translator.core.translator.backends.openrouter_api import OpenRouterBackend

def test_is_available_with_key():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test"}):
        assert OpenRouterBackend().is_available() is True

def test_is_available_without_key():
    with patch.dict(os.environ, {}, clear=True):
        assert OpenRouterBackend().is_available() is False

def test_translate_success():
    backend = OpenRouterBackend()
    mock_response = json.dumps([{"index": 0, "text": "안녕"}])
    with patch.object(backend, "_call_api", return_value=mock_response):
        result = backend.translate(["Hello"], "en", "ko")
        assert result == ["안녕"]

def test_name_and_type():
    b = OpenRouterBackend()
    assert b.name == "openrouter"
    assert b.backend_type == "api"
```

- [ ] **Step 2: Implement all 4 API backends**

Each backend uses `requests` (no heavy SDK dependency) with the OpenAI-compatible chat completions format. This keeps dependencies minimal.

**openai_api.py:**
```python
# pdf_translator/core/translator/backends/openai_api.py
from __future__ import annotations
import json, logging, os
import requests
from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)

class OpenAIBackend:
    name = "openai-api"
    backend_type = "api"

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def is_available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def translate(self, texts, source_lang, target_lang, glossary=None):
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._call_api(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)

    def _call_api(self, prompt: str) -> str:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        try:
            resp = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("OpenAI API failed: %s", e)
            return ""
```

**anthropic_api.py:**
```python
# pdf_translator/core/translator/backends/anthropic_api.py
from __future__ import annotations
import json, logging, os
import requests
from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)

class AnthropicBackend:
    name = "anthropic-api"
    backend_type = "api"

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self.api_url = "https://api.anthropic.com/v1/messages"

    def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def translate(self, texts, source_lang, target_lang, glossary=None):
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._call_api(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)

    def _call_api(self, prompt: str) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        try:
            resp = requests.post(
                self.api_url,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "max_tokens": 4096,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        except Exception as e:
            logger.warning("Anthropic API failed: %s", e)
            return ""
```

**google_api.py:**
```python
# pdf_translator/core/translator/backends/google_api.py
from __future__ import annotations
import json, logging, os
import requests
from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)

class GoogleAPIBackend:
    name = "google-api"
    backend_type = "api"

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model

    def is_available(self) -> bool:
        return bool(os.environ.get("GOOGLE_API_KEY"))

    def translate(self, texts, source_lang, target_lang, glossary=None):
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._call_api(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)

    def _call_api(self, prompt: str) -> str:
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
        try:
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.1}},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.warning("Google API failed: %s", e)
            return ""
```

**openrouter_api.py:**
```python
# pdf_translator/core/translator/backends/openrouter_api.py
from __future__ import annotations
import json, logging, os
import requests
from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)

class OpenRouterBackend:
    name = "openrouter"
    backend_type = "api"

    def __init__(self, model: str = "anthropic/claude-sonnet-4"):
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def is_available(self) -> bool:
        return bool(os.environ.get("OPENROUTER_API_KEY"))

    def translate(self, texts, source_lang, target_lang, glossary=None):
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._call_api(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)

    def _call_api(self, prompt: str) -> str:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        try:
            resp = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("OpenRouter API failed: %s", e)
            return ""
```

- [ ] **Step 3: Run all backend tests**

Run: `python -m pytest tests/test_backend_openai.py tests/test_backend_anthropic.py tests/test_backend_google_api.py tests/test_backend_openrouter.py -v`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: add OpenAI, Anthropic, Google, OpenRouter API backends"
```

---

## Task 4: Register API backends in Router

**Files:**
- Modify: `pdf_translator/core/translator/router.py`, `pdf_translator/core/translator/backends/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update router.py to include API backends**

In `BackendRouter.__init__`, add API backends after CLI backends:

```python
from pdf_translator.core.translator.backends.openai_api import OpenAIBackend
from pdf_translator.core.translator.backends.anthropic_api import AnthropicBackend
from pdf_translator.core.translator.backends.google_api import GoogleAPIBackend
from pdf_translator.core.translator.backends.openrouter_api import OpenRouterBackend

# In __init__:
self._api_backends = [OpenRouterBackend(), OpenAIBackend(), AnthropicBackend(), GoogleAPIBackend()]
```

Update `_all_backends` to include API backends.

- [ ] **Step 2: Update backends/__init__.py**

Add exports for the 4 new backends.

- [ ] **Step 3: Add `requests` to dependencies and optional `[api]` group in pyproject.toml**

```toml
dependencies = [
    "opendataloader-pdf>=0.3",
    "PyMuPDF>=1.24",
    "rich>=13.0",
    "langdetect>=1.0.9",
    "deep-translator>=1.11",
    "requests>=2.28",
]

[project.optional-dependencies]
api = ["openai>=1.0", "anthropic>=0.20"]
```

- [ ] **Step 4: Run router tests + full suite**

Run: `python -m pytest tests/test_router.py tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: register API backends in router, add requests dependency"
```

---

## Task 5: CLI Integration (glossary + draft flags)

**Files:**
- Modify: `pdf_translator/core/config.py`, `pdf_translator/cli/main.py`, `pdf_translator/core/__init__.py`
- Test: `tests/test_cli.py` (update)

- [ ] **Step 1: Add fields to TranslatorConfig**

```python
# Add to TranslatorConfig:
glossary: str | None = None
draft_only: bool = False
build_from: str | None = None
retranslate: str | None = None
```

- [ ] **Step 2: Add CLI flags to parse_args**

```python
parser.add_argument("--glossary", default=None, help="Glossary CSV path or built-in pack name")
parser.add_argument("--draft-only", action="store_true", help="Save draft JSON only, skip PDF build")
parser.add_argument("--build-from", default=None, help="Build PDF from draft JSON")
parser.add_argument("--retranslate", default=None, help="Retranslate pending items in draft JSON")
```

Make `input` argument optional (not needed for --build-from or --retranslate):
```python
parser.add_argument("input", nargs="?", default=None, help="Input PDF file path")
```

- [ ] **Step 3: Update run() to handle glossary and draft modes**

Three modes in `run()`:
1. `--build-from draft.json` → load draft, build PDF/MD
2. `--retranslate draft.json --backend X` → load draft, re-translate pending, save draft
3. Default → extract, translate (with glossary), optionally save draft or build output

- [ ] **Step 4: Update translate_pdf() in core/__init__.py**

Pass glossary through the pipeline. Load glossary with `load_glossary()`, convert to prompt dict, pass to `translate_all`.

- [ ] **Step 5: Update translate_all to accept glossary**

Add `glossary: dict[str, str] | None = None` parameter to `translate_all()` and pass it through to worker items.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: add --glossary, --draft-only, --build-from, --retranslate CLI flags"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Glossary system (3-tier + built-in packs) | `core/glossary.py`, `data/glossaries/*.csv` |
| 2 | Draft system (JSON save/load/edit) | `core/draft.py` |
| 3 | API backends (OpenAI, Anthropic, Google, OpenRouter) | `backends/*_api.py` |
| 4 | Register API backends in Router | `router.py`, `pyproject.toml` |
| 5 | CLI integration (glossary + draft flags) | `cli/main.py`, `core/config.py` |

**After Phase 2 completion:**
- `pdf-translator paper.pdf --glossary ml-ai` — ML 용어집 적용 번역
- `pdf-translator paper.pdf --glossary terms.csv --draft-only` — Draft만 저장
- `pdf-translator --build-from draft.json` — Draft에서 PDF 빌드
- `pdf-translator paper.pdf --backend openai-api` — OpenAI API로 번역
- `pdf-translator paper.pdf --backend openrouter` — OpenRouter로 번역

**Next plans:** Phase 3 (OCR), Phase 4 (web UI).
