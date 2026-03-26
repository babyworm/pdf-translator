from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


class TranslationCache:
    def __init__(self, db_path: Path | str):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS translations (
                source_hash TEXT NOT NULL,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                translated TEXT NOT NULL,
                PRIMARY KEY (source_hash, source_lang, target_lang)
            )"""
        )
        self._conn.commit()

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def get(self, source: str, source_lang: str, target_lang: str) -> str | None:
        row = self._conn.execute(
            "SELECT translated FROM translations WHERE source_hash=? AND source_lang=? AND target_lang=?",
            (self._hash(source), source_lang, target_lang),
        ).fetchone()
        return row[0] if row else None

    def put(self, source: str, source_lang: str, target_lang: str, translated: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO translations (source_hash, source_lang, target_lang, translated) VALUES (?, ?, ?, ?)",
            (self._hash(source), source_lang, target_lang, translated),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
