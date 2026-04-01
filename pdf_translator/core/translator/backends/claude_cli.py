from __future__ import annotations

import logging
import shutil
import subprocess
import time

from pdf_translator.core.translator.base import build_prompt, parse_response

logger = logging.getLogger(__name__)


class ClaudeCLIBackend:
    name = "claude-cli"
    backend_type = "cli"

    def __init__(self, model: str = "sonnet", max_retries: int = 2):
        self.model = model
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def translate(self, texts, source_lang, target_lang, glossary=None):
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
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
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
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
            except (subprocess.TimeoutExpired, OSError):
                logger.warning("Claude CLI failed (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                if attempt < self.max_retries:
                    time.sleep(min(0.5 * (2 ** attempt), 4.0))
        return ""
