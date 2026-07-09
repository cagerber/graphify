"""Tests for graphify.paths (GRAPHIFY_OUT resolution and test-path classifier)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from graphify.paths import (
    _is_test_path,
    disambiguate_ambiguous_candidates,
)


@pytest.mark.unit
def test_manifest_path_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GRAPHIFY_OUT", ".local/graphify-out")
    from graphify.paths import graphify_out_dir, manifest_path, skip_dir_names

    assert graphify_out_dir() == tmp_path / ".local" / "graphify-out"
    assert manifest_path() == str(tmp_path / ".local" / "graphify-out" / "manifest.json")
    assert "graphify-out" in skip_dir_names()
    assert ".local" in skip_dir_names()


@pytest.mark.unit
def test_graphify_out_for_watch_uses_project_root_not_subpath(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "reference").mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GRAPHIFY_OUT", ".local/graphify-out")
    from graphify.paths import graphify_out_for_watch

    assert graphify_out_for_watch(Path("reference")) == repo / ".local" / "graphify-out"
    assert graphify_out_for_watch(Path(".")) == repo / ".local" / "graphify-out"


@pytest.mark.unit
def test_detect_save_manifest_uses_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GRAPHIFY_OUT", "custom-out")
    from graphify.detect import save_manifest

    save_manifest({"code": []}, root=tmp_path, kind="ast")
    assert (tmp_path / "custom-out" / "manifest.json").is_file()


@pytest.mark.parametrize(
    "path",
    [
        "tests/foo.py",
        "src/tests/foo.py",
        "test/foo.go",
        "spec/foo.rb",
        "specs/foo.rb",
        "app/__tests__/foo.js",
        "a/b/TESTS/foo.py",
        "src/test_service.py",
        "pkg/service_test.go",
        "src/service.test.ts",
        "src/service.spec.ts",
        "src/service_spec.rb",
        "ps/Module.Tests.ps1",
        "java/FooTest.java",
        "java/FooTests.java",
        "cs/FooTests.cs",
        "src\\tests\\foo.py",
        "src\\service_test.py",
    ],
)
def test_is_test_path_positive(path: str) -> None:
    assert _is_test_path(path) is True, path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "latest.py",
        "contest.py",
        "src/contest.py",
        "src/greatest/x.py",
        "src/service.py",
        "lib/helper.go",
        "src/attestation.py",
        "src/testimony.py",
        "src/contest/x.py",
        "src/greatest.cs",
        "src/protest.java",
        "config/manifest.json",
    ],
)
def test_is_test_path_negative(path: str) -> None:
    assert _is_test_path(path) is False, path


def test_disambiguate_drops_test_candidate_for_nontest_call_site() -> None:
    winner = disambiguate_ambiguous_candidates(
        ["src", "mock"],
        {"src": "src/service.py", "mock": "tests/test_service.py"},
        "src/caller.py",
    )
    assert winner == "src"


def test_disambiguate_bails_on_two_nontest_candidates() -> None:
    winner = disambiguate_ambiguous_candidates(
        ["a", "b"],
        {"a": "alpha/a.py", "b": "beta/b.py"},
        "pkg/caller.py",
    )
    assert winner is None


def test_disambiguate_test_call_site_prefers_test_local() -> None:
    winner = disambiguate_ambiguous_candidates(
        ["src", "local"],
        {"src": "src/service.py", "local": "tests/test_service.py"},
        "tests/test_service.py",
    )
    assert winner == "local"


def test_disambiguate_path_proximity_same_dir() -> None:
    winner = disambiguate_ambiguous_candidates(
        ["near", "far"],
        {"near": "pkg/a/service.py", "far": "pkg/b/service.py"},
        "pkg/a/caller.py",
    )
    assert winner == "near"
