"""Tests for [tool.graphify] enrich flags and env overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from graphify.config import enrich_flags, load_graphify_config


@pytest.mark.unit
def test_enrich_flags_defaults() -> None:
    flags = enrich_flags()
    assert flags["folder_edges"] is True
    assert flags["folder_affinity"] is True
    assert flags["pytest_enrich"] is True
    assert flags["heuristic_labels"] is False


@pytest.mark.unit
def test_enrich_flags_from_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.graphify]
folder_edges = false
folder_affinity = false
pytest_enrich = false
heuristic_labels = true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "GRAPHIFY_FOLDER_EDGES",
        "GRAPHIFY_FOLDER_AFFINITY",
        "GRAPHIFY_PYTEST_ENRICH",
        "GRAPHIFY_HEURISTIC_LABELS",
    ):
        monkeypatch.delenv(key, raising=False)
    flags = enrich_flags(tmp_path)
    assert flags == {
        "folder_edges": False,
        "folder_affinity": False,
        "pytest_enrich": False,
        "heuristic_labels": True,
    }


@pytest.mark.unit
def test_enrich_flags_env_overrides_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[tool.graphify]\nheuristic_labels = false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GRAPHIFY_HEURISTIC_LABELS", "1")
    assert enrich_flags(tmp_path)["heuristic_labels"] is True


@pytest.mark.unit
def test_load_graphify_config_parses_bools(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.graphify]\nfolder_edges = false\n",
        encoding="utf-8",
    )
    cfg = load_graphify_config(tmp_path)
    assert cfg.folder_edges is False
