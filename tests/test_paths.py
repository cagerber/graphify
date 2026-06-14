"""Tests for graphify.paths (GRAPHIFY_OUT resolution)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


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
