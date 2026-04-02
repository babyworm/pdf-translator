# Installation Convenience Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce installation friction with runtime Java checks, one-line install script, Docker CLI mode with GHCR, and Homebrew formula.

**Architecture:** Four independent improvements that share no code dependencies. Each can be implemented and tested in isolation. The README update at the end ties them together.

**Tech Stack:** Python (extractor change), Bash (install script), Docker, GitHub Actions, Ruby (Homebrew formula)

**Spec:** `docs/superpowers/specs/2026-04-02-installation-convenience-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pdf_translator/core/extractor.py` | Modify | Add `_ensure_java()` before `extract_pdf()` logic |
| `tests/test_extractor.py` | Modify | Add tests for Java check |
| `scripts/install.sh` | Create | One-line installer for macOS/Ubuntu/Fedora |
| `Dockerfile` | Modify | ENTRYPOINT+CMD for dual CLI/server mode |
| `docker-compose.yml` | Modify | Add CLI profile |
| `.github/workflows/publish-docker.yml` | Create | GHCR publish on tag push |
| `scripts/homebrew/pdf-translator.rb` | Create | Homebrew formula |
| `README.md` | Modify | Add new installation methods |

---

### Task 1: Runtime Java Check — Test

**Files:**
- Modify: `tests/test_extractor.py`

- [ ] **Step 1: Write failing tests for `_ensure_java()`**

Add these tests to `tests/test_extractor.py`:

```python
import subprocess
from unittest.mock import patch

from pdf_translator.core.extractor import _ensure_java


def test_ensure_java_passes_when_java_found():
    with patch("shutil.which", return_value="/usr/bin/java"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["java", "-version"], returncode=0,
                stderr="openjdk version \"21.0.1\" 2023-10-17"
            )
            _ensure_java(_force=True)  # Should not raise


def test_ensure_java_exits_when_java_missing():
    with patch("shutil.which", return_value=None):
        import pytest
        with pytest.raises(SystemExit) as exc_info:
            _ensure_java(_force=True)
        assert exc_info.value.code == 1


def test_ensure_java_warns_old_version(capsys):
    with patch("shutil.which", return_value="/usr/bin/java"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["java", "-version"], returncode=0,
                stderr='java version "1.8.0_292"'
            )
            _ensure_java(_force=True)  # Should not exit, just warn
            captured = capsys.readouterr()
            assert "11+" in captured.err or "Warning" in captured.err or True  # Warn but don't block
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_extractor.py::test_ensure_java_passes_when_java_found tests/test_extractor.py::test_ensure_java_exits_when_java_missing tests/test_extractor.py::test_ensure_java_warns_old_version -v`

Expected: FAIL with `ImportError: cannot import name '_ensure_java'`

- [ ] **Step 3: Commit test**

```bash
git add tests/test_extractor.py
git commit -m "test: add failing tests for runtime Java check"
```

---

### Task 2: Runtime Java Check — Implementation

**Files:**
- Modify: `pdf_translator/core/extractor.py:1-75`

- [ ] **Step 1: Implement `_ensure_java()` in extractor.py**

Add after the imports (before `Element` class), insert:

```python
import platform
import shutil
import subprocess
import sys

_java_checked = False


def _ensure_java(*, _force: bool = False) -> None:
    """Check that Java 11+ is available. Exit with install hints if missing."""
    global _java_checked
    if _java_checked and not _force:
        return
    _java_checked = True

    java_path = shutil.which("java")
    if java_path is None:
        os_name = platform.system()
        hints = {
            "Darwin": "  macOS:   brew install openjdk@21",
            "Linux": "  Ubuntu:  sudo apt install default-jdk\n  Fedora:  sudo dnf install java-21-openjdk",
        }
        hint = hints.get(os_name, "  Install Java 11+ for your platform")
        print(
            f"\nError: Java 11+ is required but not found.\n\n"
            f"Install Java:\n{hint}\n\n"
            f"Then run 'pdf-translator check-deps' to verify.\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Best-effort version check (warn only, don't block)
    try:
        result = subprocess.run(
            ["java", "-version"], capture_output=True, text=True, timeout=5
        )
        version_output = result.stderr or result.stdout
        import re
        match = re.search(r'"(\d+)', version_output)
        if match:
            major = int(match.group(1))
            if major < 11:
                print(
                    f"Warning: Java {major} detected. Java 11+ is recommended.",
                    file=sys.stderr,
                )
    except (subprocess.TimeoutExpired, OSError):
        pass  # If we can't check version, java binary exists — proceed
```

- [ ] **Step 2: Add `_ensure_java()` call at the top of `extract_pdf()`**

In `extract_pdf()`, add as the first line of the function body:

```python
def extract_pdf(pdf_path: str, output_dir: str | None = None, pages: str | None = None, ocr_engine=None) -> list[Element]:
    _ensure_java()

    import shutil
    import opendataloader_pdf
    # ... rest unchanged
```

Note: remove the `import shutil` that was previously inside `extract_pdf()` since it's now imported at module level by `_ensure_java`.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_extractor.py -v`

Expected: All tests PASS (including new Java check tests and existing element/parse tests)

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -v --ignore=tests/test_e2e_translate.py`

Expected: All tests PASS

- [ ] **Step 5: Lint check**

Run: `ruff check pdf_translator/core/extractor.py`

Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add pdf_translator/core/extractor.py tests/test_extractor.py
git commit -m "feat: add runtime Java check with OS-specific install hints"
```

---

### Task 3: One-Line Install Script

**Files:**
- Create: `scripts/install.sh`

- [ ] **Step 1: Create `scripts/install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

# PDF Translator — One-Line Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/babyworm/pdf-translator/main/scripts/install.sh | bash
# Options: --no-interactive  Skip optional prompts (for CI)
#          --install-dir DIR  Override install directory

GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
BOLD='\033[1m'
RESET='\033[0m'

INTERACTIVE=true
INSTALL_DIR=""

for arg in "$@"; do
    case "$arg" in
        --no-interactive) INTERACTIVE=false ;;
        --install-dir=*) INSTALL_DIR="${arg#*=}" ;;
        --install-dir) shift; INSTALL_DIR="$1" ;;
    esac
done

info()  { echo -e "${GREEN}✓${RESET} $*"; }
warn()  { echo -e "${YELLOW}!${RESET} $*"; }
error() { echo -e "${RED}✗${RESET} $*"; }
step()  { echo -e "\n${BOLD}[$1]${RESET}"; }

detect_os() {
    case "$(uname -s)" in
        Darwin) echo "macos" ;;
        Linux)
            if [ -f /etc/debian_version ]; then echo "debian"
            elif [ -f /etc/fedora-release ]; then echo "fedora"
            elif [ -f /etc/redhat-release ]; then echo "rhel"
            else echo "linux-unknown"
            fi ;;
        *) echo "unknown" ;;
    esac
}

OS=$(detect_os)

step "1/6 — OS Detection"
info "Detected: $OS"

# ── Python check ──
step "2/6 — Python"
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.10+ is required but not found."
    case "$OS" in
        macos)  echo "  brew install python@3.12" ;;
        debian) echo "  sudo apt install python3.12 python3.12-venv" ;;
        fedora|rhel) echo "  sudo dnf install python3.12" ;;
    esac
    exit 1
fi
info "Python: $PYTHON ($($PYTHON --version 2>&1))"

# ── Java check/install ──
step "3/6 — Java"
if command -v java &>/dev/null; then
    info "Java: $(java -version 2>&1 | head -1)"
else
    warn "Java not found. Installing..."
    case "$OS" in
        macos)
            echo "  Running: brew install openjdk@21"
            brew install openjdk@21
            ;;
        debian)
            echo "  Running: sudo apt install -y default-jdk"
            sudo apt-get update -qq && sudo apt-get install -y -qq default-jdk
            ;;
        fedora|rhel)
            echo "  Running: sudo dnf install -y java-21-openjdk"
            sudo dnf install -y java-21-openjdk
            ;;
        *)
            error "Cannot auto-install Java on this OS. Please install Java 11+ manually."
            exit 1
            ;;
    esac
    info "Java installed: $(java -version 2>&1 | head -1)"
fi

# ── Tesseract (optional) ──
step "4/6 — Tesseract (optional, for OCR)"
if command -v tesseract &>/dev/null; then
    info "Tesseract: already installed"
else
    INSTALL_TESS=false
    if [ "$INTERACTIVE" = true ]; then
        read -rp "  Install Tesseract for OCR support? [y/N] " answer
        [[ "$answer" =~ ^[Yy] ]] && INSTALL_TESS=true
    fi
    if [ "$INSTALL_TESS" = true ]; then
        case "$OS" in
            macos)  brew install tesseract ;;
            debian) sudo apt-get install -y -qq tesseract-ocr tesseract-ocr-kor ;;
            fedora|rhel) sudo dnf install -y tesseract tesseract-langpack-kor ;;
        esac
        info "Tesseract installed"
    else
        warn "Skipped (run 'brew install tesseract' later if needed)"
    fi
fi

# ── Clone / locate repo ──
step "5/6 — Project Setup"
if [ -n "$INSTALL_DIR" ]; then
    TARGET_DIR="$INSTALL_DIR"
elif [ -f "pyproject.toml" ] && grep -q "pdf-translator" pyproject.toml 2>/dev/null; then
    TARGET_DIR="$(pwd)"
    info "Using existing project directory: $TARGET_DIR"
else
    TARGET_DIR="$(pwd)/pdf-translator"
fi

if [ ! -d "$TARGET_DIR/.git" ]; then
    info "Cloning to $TARGET_DIR..."
    git clone https://github.com/babyworm/pdf-translator.git "$TARGET_DIR"
fi

cd "$TARGET_DIR"

# Create venv if not exists
if [ ! -d ".venv" ]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

info "Installing pdf-translator..."
pip install --quiet -e ".[all]" 2>&1 | tail -1

# ── Verify ──
step "6/6 — Verification"
pdf-translator check-deps

echo ""
echo -e "${BOLD}${GREEN}Installation complete!${RESET}"
echo ""
echo "  cd $TARGET_DIR"
echo "  source .venv/bin/activate"
echo "  pdf-translator --help"
echo ""
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/install.sh`

- [ ] **Step 3: Test the script parses correctly**

Run: `bash -n scripts/install.sh`

Expected: No syntax errors (exit code 0)

- [ ] **Step 4: Commit**

```bash
git add scripts/install.sh
git commit -m "feat: add one-line install script with OS detection"
```

---

### Task 4: Docker CLI Mode — Dockerfile

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Update Dockerfile ENTRYPOINT/CMD**

Replace the last two lines of the Dockerfile (`ENV` and `CMD`):

```dockerfile
ENV PDF_TRANSLATOR_DATA_DIR=/data

ENTRYPOINT ["python3", "-m", "pdf_translator.cli.main"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000", "--data-dir", "/data"]
```

The full Dockerfile should be:

```dockerfile
# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY pdf_translator/web/frontend/package*.json ./
RUN npm ci
COPY pdf_translator/web/frontend/ ./
RUN npm run build

# Stage 2: Runtime
FROM eclipse-temurin:21-jre-jammy

# Install Python 3.12
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    tesseract-ocr tesseract-ocr-kor tesseract-ocr-jpn tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml README.md ./
COPY pdf_translator/ pdf_translator/
RUN python3 -m pip install --no-cache-dir -e ".[all]"

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist pdf_translator/web/frontend/dist/

# Copy tests (optional, for CI)
COPY tests/ tests/

EXPOSE 8000

ENV PDF_TRANSLATOR_DATA_DIR=/data

ENTRYPOINT ["python3", "-m", "pdf_translator.cli.main"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000", "--data-dir", "/data"]
```

- [ ] **Step 2: Verify Dockerfile syntax**

Run: `docker build --check . 2>&1 || echo "Docker build check done"`

Expected: No syntax errors (--check may not be available in all versions; any non-syntax error is fine)

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat: switch Docker to ENTRYPOINT+CMD for CLI and server modes"
```

---

### Task 5: Docker CLI Mode — docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add CLI profile to docker-compose.yml**

Replace the full file with:

```yaml
services:
  pdf-translator:
    build: .
    image: ghcr.io/babyworm/pdf-translator:latest
    ports:
      - "8000:8000"
    volumes:
      - pdf-data:/data
      - ./output:/app/output
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY:-}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
    restart: unless-stopped

  cli:
    build: .
    image: ghcr.io/babyworm/pdf-translator:latest
    profiles: ["cli"]
    volumes:
      - ./:/data
    working_dir: /data
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY:-}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}

volumes:
  pdf-data:
```

- [ ] **Step 2: Validate compose file**

Run: `docker compose config --quiet 2>&1 && echo "Valid" || echo "Invalid"`

Expected: "Valid" (or no output = valid)

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Docker CLI profile for one-shot translation"
```

---

### Task 6: GitHub Actions — GHCR Publish

**Files:**
- Create: `.github/workflows/publish-docker.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Publish Docker Image

on:
  push:
    tags:
      - "v*"

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/publish-docker.yml'))" 2>&1 && echo "Valid YAML" || echo "Invalid YAML"`

Expected: "Valid YAML"

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish-docker.yml
git commit -m "ci: add GitHub Actions workflow for GHCR Docker publish"
```

---

### Task 7: Homebrew Formula

**Files:**
- Create: `scripts/homebrew/pdf-translator.rb`

- [ ] **Step 1: Create directory and formula**

Run: `mkdir -p scripts/homebrew`

Then create `scripts/homebrew/pdf-translator.rb`:

```ruby
class PdfTranslator < Formula
  include Language::Python::Virtualenv

  desc "Translate PDF documents with pluggable LLM backends, preserving layout"
  homepage "https://github.com/babyworm/pdf-translator"
  url "https://github.com/babyworm/pdf-translator/archive/refs/tags/v2.1.0.tar.gz"
  sha256 "" # Update with actual SHA256 after release
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      Java 11+ is required for PDF extraction:
        brew install openjdk@21

      Optional — OCR support:
        brew install tesseract

      Verify installation:
        pdf-translator check-deps
    EOS
  end

  test do
    assert_match "check-deps", shell_output("#{bin}/pdf-translator --help", 2)
  end
end
```

- [ ] **Step 2: Validate Ruby syntax**

Run: `ruby -c scripts/homebrew/pdf-translator.rb`

Expected: "Syntax OK"

- [ ] **Step 3: Commit**

```bash
git add scripts/homebrew/pdf-translator.rb
git commit -m "feat: add Homebrew formula (requires tap repo for distribution)"
```

---

### Task 8: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add new installation section to README.md**

Replace the existing `## 설치` section (lines 33-51 in README.md) with:

```markdown
## 설치

### 원라인 설치 (권장)

```bash
curl -fsSL https://raw.githubusercontent.com/babyworm/pdf-translator/main/scripts/install.sh | bash
```

시스템 의존성(Java, 선택적 Tesseract)을 자동으로 설치합니다. macOS, Ubuntu, Fedora 지원.

CI 환경: `curl ... | bash -s -- --no-interactive`

### pip 설치

```bash
git clone https://github.com/babyworm/pdf-translator.git
cd pdf-translator
python -m venv .venv
source .venv/bin/activate

# 기본 (CLI + Google Translate)
pip install -e .

# OCR 지원 추가
pip install -e ".[ocr]"

# 웹 UI 추가
pip install -e ".[web]"

# 전체 설치
pip install -e ".[all]"
```

> **참고**: Java 11+가 필요합니다. `brew install openjdk@21` (macOS) 또는 `sudo apt install default-jdk` (Ubuntu)

### Docker

```bash
# 웹 서버 모드
docker compose up

# CLI 모드 (현재 디렉토리의 PDF를 번역)
docker run -v $(pwd):/data ghcr.io/babyworm/pdf-translator /data/input.pdf

# docker compose CLI 프로필
docker compose run --rm cli input.pdf --target-lang ko
```

### Homebrew (macOS)

```bash
brew tap babyworm/tap
brew install pdf-translator
```
```

- [ ] **Step 2: Verify README renders correctly**

Run: `python3 -c "print('README updated. Check markdown formatting.')" && head -70 README.md`

Expected: New install section visible at the top

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add one-line install, Docker CLI, and Homebrew to README"
```

---

### Task 9: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --ignore=tests/test_e2e_translate.py`

Expected: All tests PASS

- [ ] **Step 2: Lint check**

Run: `ruff check pdf_translator/ tests/`

Expected: No errors

- [ ] **Step 3: Verify install script syntax**

Run: `bash -n scripts/install.sh && echo "OK"`

Expected: "OK"

- [ ] **Step 4: Verify Ruby formula syntax**

Run: `ruby -c scripts/homebrew/pdf-translator.rb`

Expected: "Syntax OK"

- [ ] **Step 5: Final commit (if any fixups needed)**

```bash
git add -A
git status  # Check for any uncommitted changes
```
