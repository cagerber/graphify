"""Tests for structural enrich passes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphify.enrich import add_folder_edges, add_pytest_metadata_and_covers
from graphify.config import GraphifyConfig, TestsCoversRule, production_path_for_test


@pytest.mark.unit
def test_add_folder_edges_on_file_hubs() -> None:
    data = {
        "nodes": [
            {"id": "a", "label": "foo.py", "source_file": "pkg/foo.py", "kind": "file"},
            {"id": "b", "label": "bar.py", "source_file": "pkg/bar.py", "kind": "file"},
            {"id": "c", "label": "baz()", "source_file": "pkg/foo.py", "kind": "function"},
        ],
        "links": [],
    }
    counts = add_folder_edges(data)
    assert counts["same_directory"] >= 1
    inferred = [e for e in data["links"] if e.get("confidence") == "INFERRED"]
    assert inferred
    assert inferred[0]["relation"] == "same_directory"


@pytest.mark.unit
def test_pytest_markers_and_tests_covers(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "modules" / "core" / "test_exec.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        '@pytest.mark.integration\n\ndef test_run():\n    pass\n',
        encoding="utf-8",
    )
    prod_file = tmp_path / "modules" / "core" / "exec.py"
    prod_file.parent.mkdir(parents=True)
    prod_file.write_text("def run(): pass\n", encoding="utf-8")

    data = {
        "nodes": [
            {
                "id": "t1",
                "label": "test_exec.py",
                "source_file": "tests/modules/core/test_exec.py",
                "kind": "file",
            },
            {
                "id": "p1",
                "label": "exec.py",
                "source_file": "modules/core/exec.py",
                "kind": "file",
            },
        ],
        "links": [],
    }
    config = GraphifyConfig(
        test_roots=["tests"],
        tests_covers=[
            TestsCoversRule(test="tests/**/test_*.py", strip_prefix="tests/")
        ],
    )
    counts = add_pytest_metadata_and_covers(
        data, project_root=tmp_path, config=config
    )
    assert counts["marker_files"] == 1
    assert counts["tests_covers"] == 1
    markers = data["nodes"][0]["metadata"]["markers"]
    assert "integration" in markers


@pytest.mark.unit
def test_collapse_tests_dir_covers_rule() -> None:
    rule = TestsCoversRule(
        test="tools/**/tests/test_*.py",
        strip_prefix="",
        collapse_tests_dir=True,
    )
    assert (
        production_path_for_test("tools/deploy/tests/test_foo.py", rule)
        == "tools/deploy/foo.py"
    )
