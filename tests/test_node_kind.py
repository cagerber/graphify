"""Tests for node kind metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from graphify.extract import extract_python
from graphify.node_kind import finalize_node_kinds, is_file_hub_label

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.unit
def test_extract_python_sets_kind_on_nodes() -> None:
    result = extract_python(FIXTURES / "sample.py")
    kinds = {n.get("kind") for n in result["nodes"]}
    assert "file" in kinds
    assert "class" in kinds
    assert all(n.get("kind") for n in result["nodes"])


@pytest.mark.unit
def test_finalize_node_kinds_file_hub() -> None:
    nodes = [
        {
            "id": "sample_py",
            "label": "sample.py",
            "source_file": "tests/fixtures/sample.py",
        }
    ]
    finalize_node_kinds(nodes)
    assert nodes[0]["kind"] == "file"
    assert is_file_hub_label("tests/foo.py", "foo.py")
