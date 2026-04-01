
import fitz
import pytest
from fastapi.testclient import TestClient

from pdf_translator.web.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=str(tmp_path))
    return TestClient(app)


def _make_pdf(path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Hello World", fontsize=12)
    doc.save(str(path))
    doc.close()


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_project(client, tmp_path):
    pdf = tmp_path / "test.pdf"
    _make_pdf(pdf)
    with open(pdf, "rb") as f:
        resp = client.post("/api/projects", files={"file": ("test.pdf", f, "application/pdf")})
    assert resp.status_code == 201
    assert "id" in resp.json()
    assert resp.json()["filename"] == "test.pdf"


def test_list_projects(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_project_not_found(client):
    assert client.get("/api/projects/nonexistent").status_code == 404


def test_create_and_get_project(client, tmp_path):
    pdf = tmp_path / "test.pdf"
    _make_pdf(pdf)
    with open(pdf, "rb") as f:
        create_resp = client.post("/api/projects", files={"file": ("test.pdf", f, "application/pdf")})
    pid = create_resp.json()["id"]
    get_resp = client.get(f"/api/projects/{pid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["filename"] == "test.pdf"


def test_glossary_crud(client):
    # Create
    resp = client.post("/api/glossaries", json={"name": "test", "entries": {"API": "API", "method": "방법"}})
    assert resp.status_code == 201
    gid = resp.json()["id"]

    # List
    resp = client.get("/api/glossaries")
    assert len(resp.json()) >= 1

    # Get
    resp = client.get(f"/api/glossaries/{gid}")
    assert resp.json()["name"] == "test"
    assert resp.json()["entries"]["API"] == "API"

    # Update
    resp = client.put(f"/api/glossaries/{gid}", json={"name": "updated", "entries": {"API": "API"}})
    assert resp.json()["name"] == "updated"


def test_glossary_import_csv(client):
    csv_content = "source,target\nAPI,API\nmethod,방법\n"
    resp = client.post("/api/glossaries/import",
                       files={"file": ("terms.csv", csv_content.encode(), "text/csv")})
    assert resp.status_code == 201
    assert resp.json()["entries"]["API"] == "API"


def test_glossary_not_found(client):
    assert client.get("/api/glossaries/nonexistent").status_code == 404


def test_export_pdf_not_found(client, tmp_path):
    pdf = tmp_path / "test.pdf"
    _make_pdf(pdf)
    with open(pdf, "rb") as f:
        resp = client.post("/api/projects", files={"file": ("test.pdf", f, "application/pdf")})
    pid = resp.json()["id"]
    assert client.post(f"/api/projects/{pid}/export/pdf").status_code == 404


def test_draft_not_found(client, tmp_path):
    pdf = tmp_path / "test.pdf"
    _make_pdf(pdf)
    with open(pdf, "rb") as f:
        resp = client.post("/api/projects", files={"file": ("test.pdf", f, "application/pdf")})
    pid = resp.json()["id"]
    assert client.get(f"/api/projects/{pid}/draft").status_code == 404
