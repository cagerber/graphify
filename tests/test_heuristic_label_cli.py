"""`label --heuristic` must run the heuristic labeller and never an LLM."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROVIDER_PREFIXES = (
    "ANTHROPIC", "OPENAI", "GEMINI", "GOOGLE", "MOONSHOT", "DEEPSEEK",
    "AZURE", "AWS", "OLLAMA", "GRAPHIFY",
)


def _run(tmp_path: Path, *argv: str) -> tuple[subprocess.CompletedProcess, Path]:
    """Run the CLI with no backend configured and a recording `claude` on PATH."""
    marker = tmp_path / "llm-called"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    claude = bin_dir / "claude"
    claude.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 1\n", encoding="utf-8")
    claude.chmod(0o755)
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True, exist_ok=True)  # stops the .env walk
    out = project / "graphify-out"
    out.mkdir(exist_ok=True)
    nodes = [
        {"id": f"n{i}", "label": f"mod{i}.py", "source_file": f"billing/mod{i}.py",
         "file_type": "code", "community": 0}
        for i in range(3)
    ]
    (out / "graph.json").write_text(
        json.dumps({"directed": False, "multigraph": False, "graph": {},
                    "nodes": nodes, "links": []}),
        encoding="utf-8",
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(_PROVIDER_PREFIXES)}
    env["HOME"] = str(tmp_path)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    result = subprocess.run(
        [sys.executable, "-m", "graphify", *argv],
        cwd=project, env=env, capture_output=True, text=True, timeout=120,
    )
    return result, marker


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX claude shim")
@pytest.mark.parametrize("argv", [("label", "--heuristic"), ("label-communities",)])
def test_heuristic_labelling_calls_no_llm(tmp_path: Path, argv: tuple[str, ...]) -> None:
    result, marker = _run(tmp_path, *argv, ".")

    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "an LLM backend was launched"
    assert "heuristic labels written" in result.stdout
    labels = json.loads(
        (tmp_path / "project/graphify-out/.graphify_labels.json").read_text(encoding="utf-8")
    )
    assert "billing" in labels["0"]
    assert (tmp_path / "project/graphify-out/GRAPH_REPORT.md").is_file()
    assert (tmp_path / "project/graphify-out/graph.html").is_file()


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX claude shim")
@pytest.mark.parametrize("flag", ["--backend=openai", "--backend", "--graph", "--missing-only"])
def test_heuristic_labelling_refuses_flags_it_would_ignore(tmp_path: Path, flag: str) -> None:
    result, marker = _run(tmp_path, "label", "--heuristic", flag)

    assert result.returncode == 2
    assert flag.split("=")[0] in result.stderr
    assert not marker.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX claude shim")
@pytest.mark.parametrize(
    "flag", ["--heuristic=true", "--heuristic=1", "--heuristics", "--Heuristic", "-heuristic"]
)
def test_misspelled_heuristic_flag_is_refused_not_sent_to_an_llm(tmp_path: Path, flag: str) -> None:
    result, marker = _run(tmp_path, "label", flag)

    assert not marker.exists(), "an LLM backend was launched"
    assert result.returncode == 2, result.stdout + result.stderr
    assert flag in result.stderr
