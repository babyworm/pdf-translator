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
