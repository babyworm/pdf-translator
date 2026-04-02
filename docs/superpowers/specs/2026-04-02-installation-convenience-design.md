# Installation Convenience Improvements — Design Spec

**Date**: 2026-04-02
**Status**: Approved
**Scope**: 4 improvements to reduce installation friction

## Decisions

| Item | Decision |
|------|----------|
| PyPI registration | Deferred |
| Docker registry | ghcr.io/babyworm/pdf-translator |
| Homebrew Java handling | caveat only, not in depends_on |
| Java check failure behavior | Error message + install hint, then exit |

---

## 1. Runtime Java Check

**Goal**: Fail early with actionable guidance when Java is missing, instead of cryptic runtime errors from opendataloader-pdf.

### Location

`pdf_translator/core/extractor.py` — at the entry point of `extract_pdf()`.

### Behavior

1. `shutil.which("java")` to check Java presence
2. If missing: print OS-specific install hints, raise `SystemExit(1)`
3. Optional: parse `java -version` output to verify 11+

### Error Output

```
Error: Java 11+ is required but not found.

Install Java:
  macOS:   brew install openjdk@21
  Ubuntu:  sudo apt install default-jdk
  Fedora:  sudo dnf install java-21-openjdk

Then run 'pdf-translator check-deps' to verify.
```

### Design Constraints

- Check runs once per process (module-level cache via `_java_checked` flag)
- Only triggered when `extract_pdf()` is called — CLI parsing, glossary loading, and other features work without Java
- Extracted to a standalone `_ensure_java()` function for testability (mockable)

---

## 2. One-Line Install Script

**Goal**: `curl -fsSL .../install.sh | bash` installs everything including system dependencies.

### File

`scripts/install.sh`

### Flow

```
1. Detect OS (macOS / Ubuntu-Debian / Fedora-RHEL)
2. Check Python 3.10+, exit if missing
3. Check Java, install via package manager if missing (with sudo notice)
4. Ask: install tesseract? (skip in --no-interactive)
5. git clone (or reuse existing) → venv → pip install -e ".[all]"
6. Run pdf-translator check-deps
```

### Design Constraints

- `set -euo pipefail` — abort on any error
- Colored output for progress/status
- `sudo` usage announced before invocation
- Idempotent: already-installed items skipped
- `--no-interactive` flag for CI (skips optional items like tesseract)
- Install location logic:
  1. If run inside an existing `pdf-translator` git clone → use current directory
  2. Otherwise → clone to `$PWD/pdf-translator`
  3. `--install-dir <path>` flag to override
- Supports: macOS (brew), Ubuntu/Debian (apt), Fedora/RHEL (dnf)

---

## 3. Docker CLI Mode

**Goal**: Single Docker image supports both CLI one-shot translation and web server mode.

### Changes

**Dockerfile** — switch from CMD-only to ENTRYPOINT+CMD:

```dockerfile
ENTRYPOINT ["python3", "-m", "pdf_translator.cli.main"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
```

**Usage**:

- CLI: `docker run -v $(pwd):/data ghcr.io/babyworm/pdf-translator /data/input.pdf`
- Server: `docker run -p 8000:8000 ghcr.io/babyworm/pdf-translator` (uses default CMD)
- Server explicit: `docker run -p 8000:8000 ghcr.io/babyworm/pdf-translator serve`

**docker-compose.yml** — add CLI profile:

```yaml
services:
  pdf-translator:
    # existing server config unchanged

  cli:
    build: .
    profiles: ["cli"]
    volumes:
      - ./:/data
    working_dir: /data
    entrypoint: ["python3", "-m", "pdf_translator.cli.main"]
```

**CI**: `.github/workflows/publish-docker.yml` — build and push to GHCR on version tag push (`v*`).

---

## 4. Homebrew Formula

**Goal**: `brew tap babyworm/tap && brew install pdf-translator`

### File

`scripts/homebrew/pdf-translator.rb`

### Formula Design

- Source: GitHub release tarball (`/archive/refs/tags/v{version}.tar.gz`)
- `depends_on "python@3.12"`
- Java NOT in depends_on — provided as `caveats`
- Installation via `virtualenv_install_with_resources`
- Caveats mention: Java 11+ required, tesseract optional, `pdf-translator check-deps` to verify

### Deployment

- Requires separate `babyworm/homebrew-tap` repository
- Formula file kept in this project at `scripts/homebrew/pdf-translator.rb`
- Actual deployment happens at release time (needs tagged release + tarball on GitHub)

---

## Out of Scope

- PyPI registration (deferred)
- Auto-install prompt for Java (decided against — clean exit instead)
- Windows support (install.sh and brew are Unix-only; Docker covers Windows users)

## Files to Create/Modify

| File | Action |
|------|--------|
| `pdf_translator/core/extractor.py` | Modify — add `_ensure_java()` |
| `scripts/install.sh` | Create — one-line installer |
| `Dockerfile` | Modify — ENTRYPOINT+CMD |
| `docker-compose.yml` | Modify — add cli profile |
| `.github/workflows/publish-docker.yml` | Create — GHCR publish |
| `scripts/homebrew/pdf-translator.rb` | Create — brew formula |
| `README.md` | Modify — add new install methods |
