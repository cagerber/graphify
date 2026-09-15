"""Tests for heuristic community labels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphify.heuristic_labels import (
    build_heuristic_labels,
    is_placeholder,
    labels_mostly_generic,
)


@pytest.mark.unit
def test_is_placeholder() -> None:
    assert is_placeholder("Community 1")
    assert not is_placeholder("tests / core")


@pytest.mark.unit
def test_labels_mostly_generic() -> None:
    assert labels_mostly_generic({0: "Community 0", 1: "Community 1"})
    assert not labels_mostly_generic({0: "core / execution", 1: "Community 1"})


@pytest.mark.unit
def test_build_heuristic_labels_from_paths(tmp_path: Path) -> None:
    nodes = [
        {
            "id": "a",
            "community": 0,
            "source_file": "modules/core/foo.py",
            "label": "foo.py",
            "kind": "file",
        },
        {
            "id": "b",
            "community": 0,
            "source_file": "modules/core/bar.py",
            "label": "bar.py",
            "kind": "file",
        },
        {
            "id": "c",
            "community": 1,
            "source_file": "tests/test_x.py",
            "label": "test_x.py",
            "kind": "file",
        },
    ]
    communities = {0: ["a", "b"], 1: ["c"]}
    attrs = {n["id"]: n for n in nodes}
    labels = build_heuristic_labels(communities, attrs, force=True)
    assert "modules / core" in labels[0]
    assert "tests" in labels[1]
    assert not is_placeholder(labels[0])
