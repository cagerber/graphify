"""Tests for viz layer helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphify.viz_layers import build_test_file_hub_graph


@pytest.mark.unit
def test_build_test_file_hub_graph() -> None:
    data = {
        "nodes": [
            {
                "id": "t1",
                "label": "test_a.py",
                "source_file": "tests/test_a.py",
                "kind": "file",
                "community": 0,
            },
            {
                "id": "f1",
                "label": "helper()",
                "source_file": "tests/test_a.py",
                "kind": "function",
                "community": 0,
            },
            {
                "id": "p1",
                "label": "main.py",
                "source_file": "main.py",
                "kind": "file",
                "community": 1,
            },
        ],
        "links": [
            {
                "source": "t1",
                "target": "p1",
                "relation": "tests_covers",
                "confidence": "INFERRED",
            }
        ],
    }
    graph, communities = build_test_file_hub_graph(data, test_roots=["tests"])
    assert graph.number_of_nodes() == 1
    assert "t1" in graph
