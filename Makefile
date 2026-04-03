.DEFAULT_GOAL := help
.PHONY: install install-dev install-all install-all-surya uninstall uninstall-surya clean test lint check-deps help

PYTHON ?= python3
PREFIX ?= $(HOME)/.local

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install pdf-translator to $(PREFIX)/bin
	$(PYTHON) -m pip install --user --break-system-packages . 2>/dev/null || \
	$(PYTHON) -m pip install --user .
	@echo ""
	@echo "Installed to $(PREFIX)/bin/pdf-translator"
	@echo "Make sure $(PREFIX)/bin is in your PATH."

install-all: ## Install with all optional dependencies (OCR + web)
	$(PYTHON) -m pip install --user --break-system-packages ".[all]" 2>/dev/null || \
	$(PYTHON) -m pip install --user ".[all]"
	@echo ""
	@echo "Installed to $(PREFIX)/bin/pdf-translator (with OCR + web)"
	@echo "Make sure $(PREFIX)/bin is in your PATH."

install-all-surya: ## Install everything including Surya OCR (GPU, ~2GB)
	$(PYTHON) -m pip install --user --break-system-packages ".[all-surya]" 2>/dev/null || \
	$(PYTHON) -m pip install --user ".[all-surya]"
	@echo ""
	@echo "Installed to $(PREFIX)/bin/pdf-translator (with OCR + Surya + web)"
	@echo "Make sure $(PREFIX)/bin is in your PATH."

install-dev: ## Install in editable mode for development
	$(PYTHON) -m pip install -e ".[all]"

uninstall-surya: ## Remove Surya OCR and PyTorch
	$(PYTHON) -m pip uninstall -y surya-ocr torch torchvision torchaudio 2>/dev/null || true
	@echo "Surya OCR and PyTorch removed. Tesseract OCR still available."

uninstall: ## Uninstall pdf-translator
	$(PYTHON) -m pip uninstall -y pdf-translator

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info pdf_translator.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

test: ## Run tests
	$(PYTHON) -m pytest tests/

lint: ## Run linter
	$(PYTHON) -m ruff check pdf_translator/ tests/

check-deps: ## Check runtime dependencies
	pdf-translator check-deps
