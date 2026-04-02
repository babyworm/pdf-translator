from unittest.mock import MagicMock, patch

from pdf_translator.core.compare import (
    ComparisonResult,
    compare_backends,
    format_comparison_json,
    format_comparison_table,
)


def test_comparison_result_creation():
    r = ComparisonResult(original="Hello", translations={"a": "안녕", "b": "하이"})
    assert r.original == "Hello"
    assert r.translations["a"] == "안녕"


def test_compare_backends_with_mock():
    mock_backend = MagicMock()
    mock_backend.name = "mock"
    mock_backend.translate.return_value = ["안녕"]

    mock_router = MagicMock()
    mock_router.list_available.return_value = ["mock"]
    mock_router.select.return_value = mock_backend

    with patch("pdf_translator.core.compare.BackendRouter", return_value=mock_router):
        results = compare_backends(["Hello"], "en", "ko")

    assert len(results) == 1
    assert results[0].translations["mock"] == "안녕"


def test_format_comparison_table():
    results = [
        ComparisonResult(original="Hello", translations={"a": "안녕", "b": "하이"}),
    ]
    table = format_comparison_table(results, max_width=20)
    assert "Hello" in table
    assert "안녕" in table
    assert "하이" in table


def test_format_comparison_json():
    results = [
        ComparisonResult(original="Hello", translations={"a": "안녕"}),
    ]
    output = format_comparison_json(results)
    import json
    data = json.loads(output)
    assert data[0]["original"] == "Hello"
    assert data[0]["translations"]["a"] == "안녕"


def test_compare_backend_failure():
    mock_router = MagicMock()
    mock_router.list_available.return_value = ["failing"]
    mock_router.select.side_effect = RuntimeError("unavailable")

    with patch("pdf_translator.core.compare.BackendRouter", return_value=mock_router):
        results = compare_backends(["Hello"], "en", "ko")

    assert results[0].translations["failing"] is None
