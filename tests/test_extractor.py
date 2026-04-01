import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from pdf_translator.core.extractor import Element, parse_elements, extract_pdf


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
