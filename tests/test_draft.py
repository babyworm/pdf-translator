import json
import tempfile
from pathlib import Path
from pdf_translator.core.draft import Draft, DraftElement

def test_create_draft():
    elements = [
        DraftElement(index=0, type="heading", original="Hello", translated="안녕", page=1, bbox=[0,0,100,20]),
        DraftElement(index=1, type="paragraph", original="World", translated="세계", page=1, bbox=[0,20,100,40]),
    ]
    draft = Draft(source_file="test.pdf", source_lang="en", target_lang="ko", backend="claude-cli", elements=elements)
    assert len(draft.elements) == 2
    assert draft.elements[0].status == "accepted"

def test_draft_save_load(tmp_path):
    draft = Draft(source_file="test.pdf", source_lang="en", target_lang="ko", backend="codex",
                  elements=[DraftElement(index=0, type="heading", original="Hi", translated="안녕", page=1, bbox=[0,0,100,20])])
    path = tmp_path / "draft.json"
    draft.save(str(path))
    loaded = Draft.load(str(path))
    assert loaded.source_file == "test.pdf"
    assert loaded.elements[0].translated == "안녕"

def test_draft_modify_element():
    draft = Draft(source_file="test.pdf", source_lang="en", target_lang="ko", backend="codex",
                  elements=[DraftElement(index=0, type="paragraph", original="Hello", translated="안녕", page=1, bbox=[0,0,100,20])])
    draft.elements[0].user_edit = "안녕하세요"
    draft.elements[0].status = "modified"
    assert draft.elements[0].effective_translation == "안녕하세요"

def test_draft_effective_translation_default():
    el = DraftElement(index=0, type="paragraph", original="Hello", translated="안녕", page=1, bbox=[0,0,100,20])
    assert el.effective_translation == "안녕"

def test_draft_to_translations():
    draft = Draft(source_file="test.pdf", source_lang="en", target_lang="ko", backend="codex",
                  elements=[
                      DraftElement(index=0, type="heading", original="Hi", translated="안녕", page=1, bbox=[0,0,100,20]),
                      DraftElement(index=1, type="paragraph", original="World", translated="세계", page=1, bbox=[0,20,100,40], user_edit="세상", status="modified"),
                  ])
    translations = draft.to_translations()
    assert translations[0] == "안녕"
    assert translations[1] == "세상"

def test_draft_pending_indices():
    draft = Draft(source_file="test.pdf", source_lang="en", target_lang="ko", backend="codex",
                  elements=[
                      DraftElement(index=0, type="heading", original="Hi", translated="안녕", page=1, bbox=[0,0,100,20], status="accepted"),
                      DraftElement(index=1, type="paragraph", original="World", translated=None, page=1, bbox=[0,20,100,40], status="pending"),
                  ])
    assert draft.pending_indices() == [1]
