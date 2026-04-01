from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_COLUMNS = {"status", "target_lang", "source_lang", "backend", "segments_total", "segments_translated", "glossary"}
_GLOSSARY_COLUMNS = {"name", "entries_json"}


@dataclass
class Project:
    id: str
    filename: str
    source_lang: str = "auto"
    target_lang: str = "ko"
    backend: str = "auto"
    status: str = "uploaded"
    created_at: str = ""
    segments_total: int = 0
    segments_translated: int = 0
    glossary: str | None = None


class Database:
    def __init__(self, db_path: str | Path):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                source_lang TEXT DEFAULT 'auto',
                target_lang TEXT DEFAULT 'ko',
                backend TEXT DEFAULT 'auto',
                status TEXT DEFAULT 'uploaded',
                created_at TEXT,
                segments_total INTEGER DEFAULT 0,
                segments_translated INTEGER DEFAULT 0,
                glossary TEXT
            );
            CREATE TABLE IF NOT EXISTS glossaries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entries_json TEXT DEFAULT '{}',
                created_at TEXT
            );
        """)
        self._conn.commit()

    def create_project(self, filename: str, **kwargs) -> Project:
        project = Project(
            id=str(uuid.uuid4()),
            filename=filename,
            created_at=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO projects (id, filename, source_lang, target_lang, backend, status, created_at, glossary) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project.id, project.filename, project.source_lang, project.target_lang, project.backend, project.status, project.created_at, project.glossary),
            )
            self._conn.commit()
        return project

    def get_project(self, project_id: str) -> Project | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            return None
        return Project(**dict(row))

    def list_projects(self) -> list[Project]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [Project(**dict(r)) for r in rows]

    def update_project(self, project_id: str, **kwargs) -> None:
        invalid = set(kwargs) - _PROJECT_COLUMNS
        if invalid:
            raise ValueError(f"Invalid columns: {invalid}")
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [project_id]
        with self._lock:
            self._conn.execute(f"UPDATE projects SET {sets} WHERE id=?", vals)
            self._conn.commit()

    # Glossary CRUD
    def create_glossary(self, name: str, entries: dict) -> dict:
        gid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO glossaries (id, name, entries_json, created_at) VALUES (?, ?, ?, ?)",
                (gid, name, json.dumps(entries, ensure_ascii=False), now),
            )
            self._conn.commit()
        return {"id": gid, "name": name, "entries": entries, "created_at": now}

    def list_glossaries(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM glossaries ORDER BY created_at DESC").fetchall()
        return [{"id": r["id"], "name": r["name"], "entries": json.loads(r["entries_json"]), "created_at": r["created_at"]} for r in rows]

    def get_glossary(self, glossary_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM glossaries WHERE id=?", (glossary_id,)).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "name": row["name"], "entries": json.loads(row["entries_json"]), "created_at": row["created_at"]}

    def update_glossary(self, glossary_id: str, name: str | None = None, entries: dict | None = None) -> None:
        updates = {}
        if name is not None:
            updates["name"] = name
        if entries is not None:
            updates["entries_json"] = json.dumps(entries, ensure_ascii=False)
        if updates:
            invalid = set(updates) - _GLOSSARY_COLUMNS
            if invalid:
                raise ValueError(f"Invalid columns: {invalid}")
            sets = ", ".join(f"{k}=?" for k in updates)
            vals = list(updates.values()) + [glossary_id]
            with self._lock:
                self._conn.execute(f"UPDATE glossaries SET {sets} WHERE id=?", vals)
                self._conn.commit()

    def close(self):
        self._conn.close()
