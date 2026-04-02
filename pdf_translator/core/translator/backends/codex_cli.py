from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time

from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)


class CodexCLIBackend:
    name = "codex"
    backend_type = "cli"

    def __init__(self, effort: str = "low", max_retries: int = 2, timeout: int = 300):
        self.effort = effort
        self.max_retries = max_retries
        self.timeout = timeout

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

    def translate(self, texts, source_lang, target_lang, glossary=None):
        prompt = build_prompt(texts, source_lang, target_lang, glossary)
        response = self._run_cli(prompt)
        if response:
            return parse_response(response, count=len(texts))
        return [None] * len(texts)

    def translate_raw(self, prompt: str, count: int) -> str | None:
        """Send a pre-built prompt and return the raw response."""
        return self._run_cli(prompt)

    def _run_cli(self, prompt: str) -> str:
        for attempt in range(self.max_retries + 1):
            out_path = None
            try:
                out_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, prefix="codex_out_")
                out_path = out_file.name
                out_file.close()
                cmd = ["codex", "exec", "-s", "read-only", "-o", out_path]
                if self.effort:
                    cmd += ["-c", f"reasoning_effort={self.effort}"]
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    proc.communicate(input=prompt, timeout=self.timeout)
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
