import subprocess
from unittest.mock import patch

import pytest

from pdf_translator.core.extractor import Element, _ensure_java, parse_elements


def test_element_creation():
    el = Element(
        type="paragraph",
        content="Hello world",
        page_number=1,
        bbox=[72.0, 700.0, 540.0, 730.0],
        font="Arial",
        font_size=12.0,
        text_color=[0, 0, 0],
        level=None,
    )
    assert el.content == "Hello world"
    assert el.bbox == [72.0, 700.0, 540.0, 730.0]


def test_parse_elements_from_json():
    raw = {
        "file name": "test.pdf",
        "number of pages": 1,
        "kids": [
            {
                "type": "heading",
                "content": "Title",
                "page number": 1,
                "bounding box": [72.0, 700.0, 540.0, 730.0],
                "font": "Arial",
                "font size": 24,
                "text color": [0, 0, 0],
                "level": "h1",
            },
            {
                "type": "paragraph",
                "content": "Body text here.",
                "page number": 1,
                "bounding box": [72.0, 650.0, 540.0, 690.0],
                "font": "Times",
                "font size": 12,
                "text color": [0, 0, 0],
            },
        ],
    }
    elements = parse_elements(raw)
    assert len(elements) == 2
    assert elements[0].type == "heading"
    assert elements[0].level == "h1"
    assert elements[1].content == "Body text here."


def test_deduplicate_parent_child():
    """Parent element containing child text is removed, children kept."""
    raw = {
        "kids": [
            {
                "type": "paragraph",
                "content": "Hello world. This is a test.",
                "page number": 1,
                "bounding box": [72.0, 650.0, 540.0, 700.0],
                "kids": [
                    {
                        "type": "paragraph",
                        "content": "Hello world.",
                        "page number": 1,
                        "bounding box": [72.0, 650.0, 540.0, 675.0],
                    },
                    {
                        "type": "paragraph",
                        "content": "This is a test.",
                        "page number": 1,
                        "bounding box": [72.0, 675.0, 540.0, 700.0],
                    },
                ],
            },
        ],
    }
    elements = parse_elements(raw)
    texts = [e.content for e in elements]
    # Parent "Hello world. This is a test." should be removed
    assert "Hello world. This is a test." not in texts
    assert "Hello world." in texts
    assert "This is a test." in texts


def test_no_false_dedup_different_pages():
    """Elements on different pages with same text are not deduped."""
    raw = {
        "kids": [
            {
                "type": "paragraph",
                "content": "Repeated text.",
                "page number": 1,
                "bounding box": [72.0, 650.0, 540.0, 700.0],
            },
            {
                "type": "paragraph",
                "content": "Repeated text.",
                "page number": 2,
                "bounding box": [72.0, 650.0, 540.0, 700.0],
            },
        ],
    }
    elements = parse_elements(raw)
    assert len(elements) == 2


def test_ensure_java_passes_when_java_found():
    with patch("shutil.which", return_value="/usr/bin/java"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["java", "-version"], returncode=0,
                stderr="openjdk version \"21.0.1\" 2023-10-17"
            )
            _ensure_java(_force=True)  # Should not raise


def test_ensure_java_exits_when_java_missing():
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc_info:
            _ensure_java(_force=True)
        assert exc_info.value.code == 1


def test_ensure_java_warns_old_version(capsys):
    with patch("shutil.which", return_value="/usr/bin/java"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["java", "-version"], returncode=0,
                stderr='java version "1.8.0_292"'
            )
            _ensure_java(_force=True)  # Should not exit, just warn
            captured = capsys.readouterr()
            assert "Warning" in captured.err
