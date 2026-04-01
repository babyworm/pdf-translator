# Phase 4: Web UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full web application with side-by-side PDF viewer, inline translation editing, glossary management, and real-time progress tracking.

**Architecture:** FastAPI backend serves REST API + WebSocket. React + TypeScript SPA as frontend. PDF.js for original PDF rendering. Draft JSON is the bridge between backend translation and frontend editing.

**Tech Stack:** FastAPI, SQLite (via aiosqlite), WebSocket, React 18, TypeScript, TailwindCSS, PDF.js, Vite

**Spec:** `docs/superpowers/specs/2026-04-01-pdf-translator-v2-design.md` §8

**Prerequisites:** Phase 1 (core/), Phase 2 (glossary, draft system) complete.

---

## File Map

### Backend (FastAPI)

| File | Responsibility |
|------|----------------|
| `pdf_translator/web/__init__.py` | Empty init |
| `pdf_translator/web/app.py` | FastAPI application factory |
| `pdf_translator/web/models.py` | SQLite models (projects, glossaries) |
| `pdf_translator/web/api/__init__.py` | API router |
| `pdf_translator/web/api/projects.py` | Project CRUD + translation trigger |
| `pdf_translator/web/api/glossaries.py` | Glossary CRUD + CSV import |
| `pdf_translator/web/api/export.py` | PDF/MD export endpoints |
| `pdf_translator/web/ws.py` | WebSocket handler for real-time progress |
| `pdf_translator/web/tasks.py` | Background translation task runner |
| `tests/test_web_api.py` | API endpoint tests |

### Frontend (React)

| File | Responsibility |
|------|----------------|
| `pdf_translator/web/frontend/package.json` | Dependencies |
| `pdf_translator/web/frontend/vite.config.ts` | Vite config with API proxy |
| `pdf_translator/web/frontend/src/App.tsx` | Main app with routing |
| `pdf_translator/web/frontend/src/pages/ProjectList.tsx` | Project list / upload |
| `pdf_translator/web/frontend/src/pages/TranslationView.tsx` | Side-by-side main view |
| `pdf_translator/web/frontend/src/components/PdfViewer.tsx` | PDF.js original viewer |
| `pdf_translator/web/frontend/src/components/TranslatedPanel.tsx` | Translated text with inline edit |
| `pdf_translator/web/frontend/src/components/SegmentEditor.tsx` | Single segment inline editor |
| `pdf_translator/web/frontend/src/components/GlossaryPanel.tsx` | Glossary table + add/edit |
| `pdf_translator/web/frontend/src/components/StatusBar.tsx` | Progress bar + stats |
| `pdf_translator/web/frontend/src/hooks/useWebSocket.ts` | WebSocket connection hook |
| `pdf_translator/web/frontend/src/hooks/useProject.ts` | Project data fetching |
| `pdf_translator/web/frontend/src/types.ts` | TypeScript types |
| `pdf_translator/web/frontend/src/api.ts` | API client functions |

---

## Task 1: FastAPI application + project model

**Files:**
- Create: `pdf_translator/web/app.py`, `pdf_translator/web/models.py`, `pdf_translator/web/__init__.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_api.py
import pytest
from fastapi.testclient import TestClient
from pdf_translator.web.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=str(tmp_path))
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_project(client, tmp_path):
    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    with open(pdf_path, "rb") as f:
        resp = client.post("/api/projects", files={"file": ("test.pdf", f, "application/pdf")})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["filename"] == "test.pdf"


def test_list_projects(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_project_not_found(client):
    resp = client.get("/api/projects/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 2: Implement models.py**

```python
# pdf_translator/web/models.py
from __future__ import annotations
import json
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Project:
    id: str
    filename: str
    source_lang: str = "auto"
    target_lang: str = "ko"
    backend: str = "auto"
    status: str = "uploaded"  # uploaded | extracting | translating | done | error
    created_at: str = ""
    segments_total: int = 0
    segments_translated: int = 0


class Database:
    def __init__(self, db_path: str | Path):
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
                segments_translated INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS glossaries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                project_id TEXT,
                entries_json TEXT DEFAULT '{}',
                created_at TEXT
            );
        """)
        self._conn.commit()

    def create_project(self, filename: str, **kwargs) -> Project:
        project = Project(
            id=str(uuid.uuid4())[:8],
            filename=filename,
            created_at=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )
        self._conn.execute(
            "INSERT INTO projects (id, filename, source_lang, target_lang, backend, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project.id, project.filename, project.source_lang, project.target_lang, project.backend, project.status, project.created_at),
        )
        self._conn.commit()
        return project

    def get_project(self, project_id: str) -> Project | None:
        row = self._conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            return None
        return Project(**dict(row))

    def list_projects(self) -> list[Project]:
        rows = self._conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [Project(**dict(r)) for r in rows]

    def update_project(self, project_id: str, **kwargs) -> None:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [project_id]
        self._conn.execute(f"UPDATE projects SET {sets} WHERE id=?", vals)
        self._conn.commit()

    def close(self):
        self._conn.close()
```

- [ ] **Step 3: Implement app.py**

```python
# pdf_translator/web/app.py
from __future__ import annotations
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from pdf_translator.web.models import Database


def create_app(data_dir: str = "./pdf_translator_data") -> FastAPI:
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    uploads_dir = data_path / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    db = Database(data_path / "app.db")
    app = FastAPI(title="PDF Translator")
    app.state.db = db
    app.state.data_dir = data_path
    app.state.uploads_dir = uploads_dir

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/projects", status_code=201)
    async def create_project(file: UploadFile = File(...)):
        project = db.create_project(filename=file.filename or "unknown.pdf")
        project_dir = uploads_dir / project.id
        project_dir.mkdir(exist_ok=True)
        pdf_path = project_dir / file.filename
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"id": project.id, "filename": project.filename, "status": project.status}

    @app.get("/api/projects")
    def list_projects():
        projects = db.list_projects()
        return [{"id": p.id, "filename": p.filename, "status": p.status, "created_at": p.created_at} for p in projects]

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"id": project.id, "filename": project.filename, "status": project.status,
                "segments_total": project.segments_total, "segments_translated": project.segments_translated}

    return app
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pip install fastapi httpx python-multipart && python -m pytest tests/test_web_api.py -v`

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add FastAPI app with project CRUD"
```

---

## Task 2: Translation trigger + WebSocket progress

**Files:**
- Create: `pdf_translator/web/tasks.py`, `pdf_translator/web/ws.py`
- Modify: `pdf_translator/web/app.py`
- Test: `tests/test_web_api.py` (extend)

- [ ] **Step 1: Add translation trigger test**

```python
# Add to tests/test_web_api.py
def test_trigger_translate(client, tmp_path):
    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Hello", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    with open(pdf_path, "rb") as f:
        resp = client.post("/api/projects", files={"file": ("test.pdf", f, "application/pdf")})
    project_id = resp.json()["id"]

    resp = client.post(f"/api/projects/{project_id}/translate",
                       json={"target_lang": "ko", "backend": "google-translate"})
    assert resp.status_code in (200, 202)
```

- [ ] **Step 2: Implement tasks.py**

Background translation runner that:
1. Loads PDF from uploads dir
2. Calls `translate_pdf()` from core
3. Saves draft JSON to project dir
4. Updates project status in DB
5. Sends progress via WebSocket callback

```python
# pdf_translator/web/tasks.py
from __future__ import annotations
import logging
from pathlib import Path
from pdf_translator.core import translate_pdf
from pdf_translator.web.models import Database

logger = logging.getLogger(__name__)


def run_translation(
    db: Database,
    project_id: str,
    pdf_path: str,
    output_dir: str,
    target_lang: str = "ko",
    source_lang: str = "auto",
    backend: str = "auto",
    glossary: str | None = None,
    progress_callback=None,
) -> dict:
    try:
        db.update_project(project_id, status="translating")
        result = translate_pdf(
            input_path=pdf_path,
            target_lang=target_lang,
            source_lang=source_lang,
            backend=backend,
            output_dir=output_dir,
            glossary=glossary,
        )
        db.update_project(
            project_id,
            status="done",
            segments_total=result["segments_total"],
            segments_translated=result["segments_translated"],
        )
        return result
    except Exception as e:
        logger.error("Translation failed for project %s: %s", project_id, e)
        db.update_project(project_id, status="error")
        raise
```

- [ ] **Step 3: Implement ws.py**

```python
# pdf_translator/web/ws.py
from __future__ import annotations
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, project_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(project_id, []).append(ws)

    def disconnect(self, project_id: str, ws: WebSocket):
        if project_id in self._connections:
            self._connections[project_id] = [w for w in self._connections[project_id] if w is not ws]

    async def send_progress(self, project_id: str, data: dict):
        for ws in self._connections.get(project_id, []):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                pass
```

- [ ] **Step 4: Wire into app.py**

Add POST `/api/projects/{id}/translate` endpoint and WebSocket `/api/projects/{id}/ws` endpoint.

- [ ] **Step 5: Run tests, verify pass**

Run: `python -m pytest tests/test_web_api.py -v`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add translation trigger, WebSocket progress, background tasks"
```

---

## Task 3: Glossary + Draft + Export API endpoints

**Files:**
- Create: `pdf_translator/web/api/glossaries.py`, `pdf_translator/web/api/export.py`
- Modify: `pdf_translator/web/app.py`

- [ ] **Step 1: Implement glossary endpoints**

```
GET    /api/glossaries              — list all glossaries
POST   /api/glossaries              — create glossary (JSON body)
PUT    /api/glossaries/:id          — update glossary
POST   /api/glossaries/import       — import from CSV upload
```

- [ ] **Step 2: Implement draft + export endpoints**

```
GET    /api/projects/:id/draft      — get draft JSON
PATCH  /api/projects/:id/draft/:idx — update single segment (user_edit, status)
POST   /api/projects/:id/export/pdf — rebuild and download PDF
POST   /api/projects/:id/export/md  — rebuild and download Markdown
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: add glossary CRUD, draft edit, PDF/MD export endpoints"
```

---

## Task 4: React frontend scaffolding

**Files:**
- Create: `pdf_translator/web/frontend/` directory with Vite + React + TypeScript + TailwindCSS

- [ ] **Step 1: Scaffold React app**

```bash
cd pdf_translator/web
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install tailwindcss @tailwindcss/vite pdfjs-dist
```

- [ ] **Step 2: Configure Vite proxy**

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 3: Create types.ts**

```typescript
// src/types.ts
export interface Project {
  id: string
  filename: string
  status: 'uploaded' | 'extracting' | 'translating' | 'done' | 'error'
  segments_total: number
  segments_translated: number
  created_at: string
}

export interface DraftElement {
  index: number
  type: string
  original: string
  translated: string | null
  status: 'accepted' | 'modified' | 'rejected' | 'pending'
  user_edit: string | null
  page: number
  bbox: number[]
}

export interface GlossaryEntry {
  source: string
  target: string
  rule: 'keep' | 'translate'
}
```

- [ ] **Step 4: Create api.ts**

```typescript
// src/api.ts
const BASE = '/api'

export async function listProjects() {
  const res = await fetch(`${BASE}/projects`)
  return res.json()
}

export async function createProject(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/projects`, { method: 'POST', body: form })
  return res.json()
}

export async function getProject(id: string) {
  const res = await fetch(`${BASE}/projects/${id}`)
  return res.json()
}

export async function startTranslation(id: string, opts: { target_lang: string; backend: string }) {
  const res = await fetch(`${BASE}/projects/${id}/translate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  return res.json()
}

export async function getDraft(id: string) {
  const res = await fetch(`${BASE}/projects/${id}/draft`)
  return res.json()
}

export async function updateSegment(projectId: string, idx: number, data: { user_edit?: string; status?: string }) {
  const res = await fetch(`${BASE}/projects/${projectId}/draft/${idx}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return res.json()
}
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: scaffold React frontend with Vite + TailwindCSS"
```

---

## Task 5: Project list + upload page

**Files:**
- Create: `src/pages/ProjectList.tsx`, `src/App.tsx`

- [ ] **Step 1: Implement ProjectList**

Upload button with drag-and-drop. List of existing projects with status badges. Click to navigate to translation view.

- [ ] **Step 2: Implement App with routing**

```tsx
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ProjectList } from './pages/ProjectList'
import { TranslationView } from './pages/TranslationView'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProjectList />} />
        <Route path="/project/:id" element={<TranslationView />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 3: Install react-router-dom**

```bash
npm install react-router-dom
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: add project list page with upload"
```

---

## Task 6: Side-by-side translation view

**Files:**
- Create: `src/pages/TranslationView.tsx`, `src/components/PdfViewer.tsx`, `src/components/TranslatedPanel.tsx`, `src/components/SegmentEditor.tsx`

- [ ] **Step 1: Implement PdfViewer**

Uses PDF.js to render original PDF pages. Highlights corresponding segments on hover.

- [ ] **Step 2: Implement TranslatedPanel**

Displays translated segments. Each segment is hoverable (shows border) and clickable (opens SegmentEditor).

- [ ] **Step 3: Implement SegmentEditor**

Inline textarea that appears on segment click. Save button calls PATCH endpoint. Shows original text for reference.

- [ ] **Step 4: Implement TranslationView**

Layout: left panel (PdfViewer) + right panel (TranslatedPanel). Synced scrolling between panels.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add side-by-side translation view with inline editing"
```

---

## Task 7: Glossary panel + status bar

**Files:**
- Create: `src/components/GlossaryPanel.tsx`, `src/components/StatusBar.tsx`, `src/hooks/useWebSocket.ts`

- [ ] **Step 1: Implement GlossaryPanel**

Table with source/target/rule columns. Add entry form. CSV import button. Integrated into bottom panel of TranslationView.

- [ ] **Step 2: Implement StatusBar**

Progress bar showing accepted/modified/pending/failed counts. PDF export and MD export buttons.

- [ ] **Step 3: Implement useWebSocket hook**

Connects to `/api/projects/{id}/ws`. Updates progress state in real-time during translation.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: add glossary panel, status bar, WebSocket progress"
```

---

## Task 8: Build + serve integration

**Files:**
- Modify: `pdf_translator/web/app.py`, `pdf_translator/cli/main.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Build frontend**

```bash
cd pdf_translator/web/frontend && npm run build
```

Output goes to `pdf_translator/web/frontend/dist/`.

- [ ] **Step 2: Serve static files from FastAPI**

```python
# In app.py
dist_dir = Path(__file__).parent / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True))
```

- [ ] **Step 3: Add `serve` CLI command**

```bash
pdf-translator serve [--port 8000] [--host 0.0.0.0]
```

Add to CLI as a subcommand or separate entry point.

- [ ] **Step 4: Update pyproject.toml**

```toml
[project.optional-dependencies]
web = ["fastapi>=0.100", "uvicorn>=0.20", "python-multipart>=0.0.6", "aiofiles>=23.0"]
```

- [ ] **Step 5: Run and verify**

```bash
pip install -e ".[web]"
pdf-translator serve --port 8000
# Open http://localhost:8000
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add serve command, static file serving, pyproject.toml web deps"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | FastAPI app + project model | `web/app.py`, `web/models.py` |
| 2 | Translation trigger + WebSocket | `web/tasks.py`, `web/ws.py` |
| 3 | Glossary + Draft + Export API | `web/api/glossaries.py`, `web/api/export.py` |
| 4 | React scaffolding | `web/frontend/` (Vite + TS + Tailwind) |
| 5 | Project list + upload | `pages/ProjectList.tsx` |
| 6 | Side-by-side translation view | `pages/TranslationView.tsx`, components |
| 7 | Glossary panel + status bar | `GlossaryPanel.tsx`, `StatusBar.tsx` |
| 8 | Build + serve integration | `app.py` static mount, CLI serve |

**After Phase 4 completion:**
- `pdf-translator serve` — 웹 UI 시작
- Side-by-side 원본/번역 비교
- 인라인 클릭 편집
- 용어집 실시간 관리
- WebSocket 번역 진행률
- PDF/MD 내보내기
