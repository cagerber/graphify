"""GRAPHIFY_OUT narrows stale-skill version checks to project .agents/skills/graphify."""

from __future__ import annotations

from pathlib import Path

import graphify.__main__ as mainmod


def test_skill_version_check_targets_global_without_graphify_out(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GRAPHIFY_OUT", raising=False)
    monkeypatch.chdir(tmp_path)
    targets = mainmod._skill_version_check_targets()
    assert len(targets) > 1
    assert not any(str(p).startswith(str(tmp_path)) for p in targets)


def test_skill_version_check_targets_project_only_with_graphify_out(
    monkeypatch, tmp_path: Path
) -> None:
    skill_dir = tmp_path / ".agents" / "skills" / "graphify"
    skill_dir.mkdir(parents=True)
    (skill_dir / ".graphify_version").write_text("0.0.0", encoding="utf-8")
    monkeypatch.setenv("GRAPHIFY_OUT", ".local/graphify-out")
    monkeypatch.chdir(tmp_path)
    targets = mainmod._skill_version_check_targets()
    assert {p.resolve() for p in targets} == {(skill_dir / "SKILL.md").resolve()}


def test_skill_version_check_targets_empty_when_no_project_stamp(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GRAPHIFY_OUT", ".local/graphify-out")
    monkeypatch.chdir(tmp_path)
    targets = mainmod._skill_version_check_targets()
    assert targets == set()
