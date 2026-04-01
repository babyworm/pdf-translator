"""Tests for table extraction — verifies table row end sentinels."""
from pdf_translator.core.extractor import parse_elements


def test_table_rows_produce_sentinels():
    """Table rows should emit cells followed by 'table row end' sentinel."""
    raw = {
        "kids": [
            {
                "type": "table",
                "page number": 1,
                "bounding box": [72, 500, 540, 600],
                "rows": [
                    {
                        "cells": [
                            {"type": "table cell", "content": "Name", "page number": 1, "bounding box": [72, 500, 200, 520]},
                            {"type": "table cell", "content": "Age", "page number": 1, "bounding box": [200, 500, 300, 520]},
                        ]
                    },
                    {
                        "cells": [
                            {"type": "table cell", "content": "Alice", "page number": 1, "bounding box": [72, 520, 200, 540]},
                            {"type": "table cell", "content": "30", "page number": 1, "bounding box": [200, 520, 300, 540]},
                        ]
                    },
                ],
            }
        ]
    }
    elements = parse_elements(raw)

    types = [e.type for e in elements]
    assert types == [
        "table cell", "table cell", "table row end",
        "table cell", "table cell", "table row end",
    ]
    assert elements[0].content == "Name"
    assert elements[3].content == "Alice"


def test_table_row_end_has_empty_content():
    raw = {
        "kids": [
            {
                "type": "table",
                "page number": 1,
                "bounding box": [0, 0, 100, 100],
                "rows": [
                    {"cells": [{"type": "table cell", "content": "X", "page number": 1, "bounding box": [0, 0, 50, 50]}]},
                ],
            }
        ]
    }
    elements = parse_elements(raw)
    sentinel = [e for e in elements if e.type == "table row end"]
    assert len(sentinel) == 1
    assert sentinel[0].content == ""


def test_nested_content_in_table():
    """Table cells with nested kids should be collected."""
    raw = {
        "kids": [
            {
                "type": "table",
                "page number": 1,
                "bounding box": [0, 0, 100, 100],
                "rows": [
                    {
                        "cells": [
                            {
                                "type": "table cell",
                                "page number": 1,
                                "bounding box": [0, 0, 50, 50],
                                "kids": [
                                    {"type": "paragraph", "content": "Nested text", "page number": 1, "bounding box": [0, 0, 50, 50]},
                                ],
                            },
                        ]
                    },
                ],
            }
        ]
    }
    elements = parse_elements(raw)
    paragraphs = [e for e in elements if e.type == "paragraph"]
    assert len(paragraphs) == 1
    assert paragraphs[0].content == "Nested text"
