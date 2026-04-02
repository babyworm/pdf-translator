#!/usr/bin/env python3
"""Check PDF Translator dependencies and report status."""
import shutil
import sys


def check(name, test_fn, install_hint=""):
    try:
        ok = test_fn()
        status = "✓" if ok else "✗"
        color = "\033[32m" if ok else "\033[31m"
    except Exception:
        status = "✗"
        color = "\033[31m"
        ok = False
    reset = "\033[0m"
    hint = f"  → {install_hint}" if not ok and install_hint else ""
    print(f"  {color}{status}{reset} {name}{hint}")
    return ok


def main():
    print("PDF Translator — Dependency Check\n")
    all_ok = True

    print("[Core]")
    all_ok &= check("Python 3.10+", lambda: sys.version_info >= (3, 10),
                     "Python 3.10+ required")
    all_ok &= check("Java", lambda: shutil.which("java") is not None,
                     "brew install openjdk@21 (macOS) / apt install openjdk-21-jdk (Ubuntu)")
    all_ok &= check("pypdf", lambda: __import__("pypdf") and True,
                     "pip install pypdf")
    all_ok &= check("reportlab", lambda: __import__("reportlab") and True,
                     "pip install reportlab")
    all_ok &= check("rich", lambda: __import__("rich") and True,
                     "pip install rich")
    all_ok &= check("langdetect", lambda: __import__("langdetect") and True,
                     "pip install langdetect")
    all_ok &= check("deep_translator", lambda: __import__("deep_translator") and True,
                     "pip install deep-translator")
    all_ok &= check("requests", lambda: __import__("requests") and True,
                     "pip install requests")

    print("\n[CLI Backends]")
    check("Codex CLI", lambda: shutil.which("codex") is not None,
          "npm install -g @openai/codex")
    check("Claude CLI", lambda: shutil.which("claude") is not None,
          "npm install -g @anthropic-ai/claude-code")
    check("Gemini CLI", lambda: shutil.which("gemini") is not None,
          "npm install -g @google/gemini-cli")

    print("\n[API Backends]")
    import os
    check("OPENAI_API_KEY", lambda: bool(os.environ.get("OPENAI_API_KEY")),
          "export OPENAI_API_KEY=sk-...")
    check("ANTHROPIC_API_KEY", lambda: bool(os.environ.get("ANTHROPIC_API_KEY")),
          "export ANTHROPIC_API_KEY=sk-...")
    check("GOOGLE_API_KEY", lambda: bool(os.environ.get("GOOGLE_API_KEY")),
          "export GOOGLE_API_KEY=...")
    check("OPENROUTER_API_KEY", lambda: bool(os.environ.get("OPENROUTER_API_KEY")),
          "export OPENROUTER_API_KEY=sk-...")

    print("\n[OCR (optional)]")
    check("Tesseract", lambda: shutil.which("tesseract") is not None,
          "brew install tesseract (macOS) / apt install tesseract-ocr (Ubuntu)")
    check("surya-ocr", lambda: __import__("surya") and True,
          "pip install surya-ocr")
    check("Pillow", lambda: __import__("PIL") and True,
          "pip install Pillow")

    print("\n[Web UI (optional)]")
    check("FastAPI", lambda: __import__("fastapi") and True,
          "pip install pdf-translator[web]")
    check("uvicorn", lambda: __import__("uvicorn") and True,
          "pip install pdf-translator[web]")

    print()
    if all_ok:
        print("\033[32mAll core dependencies OK!\033[0m")
    else:
        print("\033[33mSome core dependencies missing. See hints above.\033[0m")


if __name__ == "__main__":
    main()
