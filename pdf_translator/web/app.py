from __future__ import annotations

import csv
import io
import json
import threading
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pdf_translator.web.models import Database

_draft_locks: dict[str, threading.Lock] = {}
_draft_locks_lock = threading.Lock()


def _get_draft_lock(project_id: str) -> threading.Lock:
    with _draft_locks_lock:
        if project_id not in _draft_locks:
            _draft_locks[project_id] = threading.Lock()
        return _draft_locks[project_id]


class TranslateRequest(BaseModel):
    target_lang: str = "ko"
    source_lang: str = "auto"
    backend: str = "auto"
    glossary_id: str | None = None


class SegmentUpdate(BaseModel):
    user_edit: str | None = None
    status: Literal["accepted", "modified", "rejected", "pending"] | None = None


class GlossaryCreate(BaseModel):
    name: str
    entries: dict[str, str]


class GlossaryUpdate(BaseModel):
    name: str | None = None
    entries: dict[str, str] | None = None


# WebSocket connection manager
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
        dead = []
        for ws in self._connections.get(project_id, []):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(project_id, ws)


def create_app(data_dir: str = "./pdf_translator_data") -> FastAPI:
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    uploads_dir = data_path / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    db = Database(data_path / "app.db")
    ws_manager = ConnectionManager()
    app = FastAPI(title="PDF Translator")
    app.state.db = db
    app.state.data_dir = data_path
    app.state.uploads_dir = uploads_dir
    app.state.ws_manager = ws_manager

    @app.on_event("shutdown")
    def shutdown():
        db.close()

    # --- Health ---
    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # --- Projects ---
    @app.post("/api/projects", status_code=201)
    async def create_project(file: UploadFile = File(...)):
        safe_name = Path(file.filename or "upload.pdf").name
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(400, "PDF file too large (max 100MB)")
        project = db.create_project(filename=safe_name)
        project_dir = uploads_dir / project.id
        project_dir.mkdir(exist_ok=True)
        pdf_path = project_dir / safe_name
        with open(pdf_path, "wb") as f:
            f.write(content)
        return {"id": project.id, "filename": project.filename, "status": project.status}

    @app.get("/api/projects")
    def list_projects():
        projects = db.list_projects()
        return [{"id": p.id, "filename": p.filename, "status": p.status,
                 "created_at": p.created_at, "segments_total": p.segments_total,
                 "segments_translated": p.segments_translated} for p in projects]

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"id": project.id, "filename": project.filename, "status": project.status,
                "source_lang": project.source_lang, "target_lang": project.target_lang,
                "backend": project.backend, "segments_total": project.segments_total,
                "segments_translated": project.segments_translated, "created_at": project.created_at}

    # --- PDF file serving ---
    @app.get("/api/projects/{project_id}/pdf")
    def get_project_pdf(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        project_dir = uploads_dir / project_id
        pdf_files = list(project_dir.glob("*.pdf"))
        if not pdf_files:
            raise HTTPException(status_code=404, detail="PDF not found")
        return FileResponse(str(pdf_files[0]), media_type="application/pdf")

    # --- Translation trigger ---
    @app.post("/api/projects/{project_id}/translate")
    def trigger_translate(project_id: str, req: TranslateRequest):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        project_dir = uploads_dir / project_id
        pdf_files = list(project_dir.glob("*.pdf"))
        if not pdf_files:
            raise HTTPException(status_code=400, detail="No PDF file found")

        pdf_path = str(pdf_files[0])
        output_dir = str(project_dir / "output")

        glossary_dict = None
        if req.glossary_id:
            g = db.get_glossary(req.glossary_id)
            if g:
                glossary_dict = g["entries"]

        db.update_project(project_id, status="translating",
                          target_lang=req.target_lang, source_lang=req.source_lang, backend=req.backend)

        def run_translation():
            try:
                from pdf_translator.core import translate_pdf
                result = translate_pdf(
                    input_path=pdf_path, target_lang=req.target_lang,
                    source_lang=req.source_lang, backend=req.backend,
                    output_dir=output_dir, glossary=glossary_dict,
                )
                # Save draft
                from pdf_translator.core.draft import Draft, DraftElement
                elements = result.get("elements", [])
                translations = result.get("translations", {})
                draft_elements = []
                for i, el in enumerate(elements):
                    if el.content.strip():
                        draft_elements.append(DraftElement(
                            index=i, type=el.type, original=el.content,
                            translated=translations.get(i, el.content),
                            page=el.page_number, bbox=el.bbox,
                        ))
                draft = Draft(source_file=project.filename, source_lang=req.source_lang,
                              target_lang=req.target_lang, backend=req.backend, elements=draft_elements)
                draft.save(str(Path(output_dir) / "draft.json"))

                db.update_project(project_id, status="done",
                                  segments_total=result["segments_total"],
                                  segments_translated=result["segments_translated"])
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Translation failed for project %s", project_id)
                db.update_project(project_id, status="error")

        thread = threading.Thread(target=run_translation, daemon=True)
        thread.start()
        return {"status": "translating", "project_id": project_id}

    # --- Draft ---
    @app.get("/api/projects/{project_id}/draft")
    def get_draft(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        draft_path = uploads_dir / project_id / "output" / "draft.json"
        if not draft_path.exists():
            raise HTTPException(status_code=404, detail="Draft not found")
        return json.loads(draft_path.read_text(encoding="utf-8"))

    @app.patch("/api/projects/{project_id}/draft/{element_idx}")
    def update_draft_element(project_id: str, element_idx: int, update: SegmentUpdate):
        draft_path = uploads_dir / project_id / "output" / "draft.json"
        if not draft_path.exists():
            raise HTTPException(status_code=404, detail="Draft not found")
        with _get_draft_lock(project_id):
            from pdf_translator.core.draft import Draft
            draft = Draft.load(str(draft_path))
            for el in draft.elements:
                if el.index == element_idx:
                    if update.user_edit is not None:
                        el.user_edit = update.user_edit
                    if update.status is not None:
                        el.status = update.status
                    draft.save(str(draft_path))
                    return {"index": el.index, "status": el.status, "user_edit": el.user_edit}
        raise HTTPException(status_code=404, detail=f"Element {element_idx} not found")

    # --- Export ---
    @app.post("/api/projects/{project_id}/export/pdf")
    def export_pdf(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        output_dir = uploads_dir / project_id / "output"
        pdf_files = list(output_dir.glob("*_translated.pdf"))
        if not pdf_files:
            raise HTTPException(status_code=404, detail="Translated PDF not found")
        return FileResponse(str(pdf_files[0]), media_type="application/pdf",
                            filename=pdf_files[0].name)

    @app.post("/api/projects/{project_id}/export/md")
    def export_md(project_id: str):
        project = db.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        output_dir = uploads_dir / project_id / "output"
        md_files = list(output_dir.glob("*_translated.md"))
        if not md_files:
            raise HTTPException(status_code=404, detail="Translated Markdown not found")
        return FileResponse(str(md_files[0]), media_type="text/markdown",
                            filename=md_files[0].name)

    # --- Glossaries ---
    @app.get("/api/glossaries")
    def list_glossaries():
        return db.list_glossaries()

    @app.post("/api/glossaries", status_code=201)
    def create_glossary(body: GlossaryCreate):
        return db.create_glossary(name=body.name, entries=body.entries)

    @app.get("/api/glossaries/{glossary_id}")
    def get_glossary(glossary_id: str):
        g = db.get_glossary(glossary_id)
        if g is None:
            raise HTTPException(status_code=404, detail="Glossary not found")
        return g

    @app.put("/api/glossaries/{glossary_id}")
    def update_glossary(glossary_id: str, body: GlossaryUpdate):
        g = db.get_glossary(glossary_id)
        if g is None:
            raise HTTPException(status_code=404, detail="Glossary not found")
        db.update_glossary(glossary_id, name=body.name, entries=body.entries)
        return db.get_glossary(glossary_id)

    @app.post("/api/glossaries/import", status_code=201)
    async def import_glossary(file: UploadFile = File(...)):
        raw = await file.read()
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(400, "Glossary file too large (max 5MB)")
        content = raw.decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        entries = {}
        for row in reader:
            source = row.get("source", "").strip()
            target = row.get("target", "").strip()
            if source:
                entries[source] = target or source
        safe_name = Path(file.filename or "imported").name
        name = Path(safe_name).stem
        return db.create_glossary(name=name, entries=entries)

    # --- WebSocket ---
    @app.websocket("/api/projects/{project_id}/ws")
    async def project_ws(project_id: str, websocket: WebSocket):
        await ws_manager.connect(project_id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(project_id, websocket)

    dist_dir = Path(__file__).parent / "frontend" / "dist"
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True))

    return app
