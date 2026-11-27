"""Nothing leaves the machine unless asked, and a project cannot choose where it goes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from graphify import llm

AMBIENT = {
    "GEMINI_API_KEY": "k",
    "ANTHROPIC_API_KEY": "k",
    "OPENAI_API_KEY": "k",
    "AWS_PROFILE": "p",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434/v1",
}

# Everything a hostile project might put in its .env.
HOSTILE_ENV = """\
OPENAI_BASE_URL=http://evil.example/v1
ANTHROPIC_BASE_URL=http://evil.example
OLLAMA_HOST=evil.example
AZURE_OPENAI_ENDPOINT=http://evil.example
OPENAI_API_KEY=their-key
HTTPS_PROXY=http://evil.example
export GRAPHIFY_ALLOW_LOCAL_PROVIDERS=1
GRAPHIFY_BACKEND=openai
GRAPHIFY_TRIAGE_BACKEND=openai
GRAPHIFY_CONFIG=evil.toml
GRAPHIFY_QUERY_LOG=/tmp/evil.log
GRAPHIFY_GOOGLE_WORKSPACE=1
PYTHONPATH=evil
"""


def _clean_env(home: Path) -> dict[str, str]:
    prefixes = (
        "ANTHROPIC", "OPENAI", "GEMINI", "GOOGLE", "MOONSHOT", "KIMI", "DEEPSEEK",
        "AZURE", "AWS", "OLLAMA", "GRAPHIFY", "HTTP_", "HTTPS_", "PYTHONPATH",
    )
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(prefixes)}
    env["HOME"] = str(home)
    return env


def _env_after_cli_import(project: Path, home: Path) -> dict[str, str]:
    code = "import json, os, graphify.__main__; print(json.dumps(dict(os.environ)))"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=project, env=_clean_env(home),
        capture_output=True, text=True, timeout=120, check=True,
    )
    return json.loads(result.stdout.splitlines()[-1])


def _project(tmp_path: Path, dotenv: str, name: str = ".env") -> Path:
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    (project / name).write_text(dotenv, encoding="utf-8")
    return project


@pytest.mark.parametrize("name", [".env", ".env.local", ".env.shared"])
def test_project_env_cannot_choose_where_data_goes(tmp_path: Path, name: str) -> None:
    seen = _env_after_cli_import(_project(tmp_path, HOSTILE_ENV, name), tmp_path)

    leaked = [
        line.removeprefix("export ").split("=")[0]
        for line in HOSTILE_ENV.splitlines()
        if line.removeprefix("export ").split("=")[0] in seen
    ]
    assert leaked == []


def test_project_env_keeps_local_settings(tmp_path: Path) -> None:
    dotenv = "GRAPHIFY_OUT=.local/graph\nGRAPHIFY_MAX_WORKERS=2\nGRAPHIFY_BACKEND=none\n"

    seen = _env_after_cli_import(_project(tmp_path, dotenv), tmp_path)

    assert seen["GRAPHIFY_OUT"] == ".local/graph"
    assert seen["GRAPHIFY_MAX_WORKERS"] == "2"
    assert seen["GRAPHIFY_BACKEND"] == "none"


@pytest.mark.parametrize("value", ["/elsewhere/out", "../outside", "a/../../outside", "~/out", "$HOME/out"])
def test_project_env_cannot_move_output_outside_the_project(tmp_path: Path, value: str) -> None:
    seen = _env_after_cli_import(_project(tmp_path, f"GRAPHIFY_OUT={value}\n"), tmp_path)

    assert "GRAPHIFY_OUT" not in seen


def test_ambient_credentials_select_no_backend(monkeypatch) -> None:
    for key, value in AMBIENT.items():
        monkeypatch.setenv(key, value)

    assert llm.detect_backend() is None


def test_labelling_without_a_request_calls_nothing(monkeypatch) -> None:
    for key, value in AMBIENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(llm, "label_communities", lambda *a, **k: pytest.fail("LLM called"))
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    labels, source = llm.generate_community_labels(None, {0: ["a"]}, quiet=True)

    assert source == "placeholder"
    assert labels == {0: "Community 0"}


def test_python_extraction_without_a_backend_calls_nothing(monkeypatch, tmp_path: Path) -> None:
    for key, value in AMBIENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MOONSHOT_API_KEY", "k")  # the old default backend
    monkeypatch.setattr(llm, "_extract_with_adaptive_retry", lambda *a, **k: pytest.fail("LLM called"))
    doc = tmp_path / "a.md"
    doc.write_text("text", encoding="utf-8")

    with pytest.raises(ValueError, match="--backend"):
        llm.extract_corpus_parallel([doc], root=tmp_path)


def test_triage_without_a_request_selects_nothing(monkeypatch) -> None:
    from graphify.prs import _resolve_triage_backend

    for key, value in AMBIENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    with pytest.raises(ValueError, match="--backend"):
        _resolve_triage_backend()
    assert _resolve_triage_backend("openai")[0] == "openai"


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX claude shim")
@pytest.mark.parametrize("command", ["label", "cluster-only"])
def test_cli_naming_without_a_backend_keeps_names_and_calls_nothing(
    tmp_path: Path, command: str,
) -> None:
    marker = tmp_path / "llm-called"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    claude = bin_dir / "claude"
    claude.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 1\n", encoding="utf-8")
    claude.chmod(0o755)
    project = _project(tmp_path, "")
    out = project / "graphify-out"
    out.mkdir()
    nodes = [
        {"id": f"n{i}", "label": f"mod{i}.py", "source_file": f"billing/mod{i}.py",
         "file_type": "code", "community": 0}
        for i in range(4)
    ]
    links = [{"source": "n0", "target": f"n{i}", "relation": "imports"} for i in (1, 2, 3)]
    (out / "graph.json").write_text(
        json.dumps({"directed": False, "multigraph": False, "graph": {},
                    "nodes": nodes, "links": links}),
        encoding="utf-8",
    )
    (out / ".graphify_labels.json").write_text('{"0": "Billing core"}', encoding="utf-8")
    env = _clean_env(tmp_path)
    env["OPENAI_API_KEY"] = "k"
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [sys.executable, "-m", "graphify", command, ".", "--no-viz"],
        cwd=project, env=env, capture_output=True, text=True, timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    labels = json.loads((out / ".graphify_labels.json").read_text(encoding="utf-8"))
    assert labels["0"] == "Billing core"


def test_importing_the_llm_module_downloads_nothing() -> None:
    code = (
        "import tiktoken\n"
        "def boom(*a, **k): raise SystemExit('tokenizer loaded at import')\n"
        "tiktoken.get_encoding = boom\n"
        "import graphify.llm\n"
    )
    pytest.importorskip("tiktoken")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stderr


def test_skill_does_not_upload_because_a_key_is_set() -> None:
    root = Path(__file__).resolve().parents[1] / "graphify"
    files = [*root.glob("skill*.md"), *root.glob("skills/**/*.md")]

    bad = [f.name for f in files if "API_KEY` IS set, use" in f.read_text(encoding="utf-8")]

    assert files and bad == []


@pytest.mark.parametrize("module", ["tree_html.py", "callflow_html.py"])
def test_generated_html_scripts_are_pinned_with_integrity(module: str) -> None:
    source = (Path(__file__).resolve().parents[1] / "graphify" / module).read_text(encoding="utf-8")
    tags = [part.split(">")[0] for part in source.split('<script src="http')[1:]]

    assert tags
    assert all('integrity="sha384-' in tag for tag in tags), tags


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX claude shim")
def test_claude_cli_never_runs_inside_the_project(monkeypatch, tmp_path: Path) -> None:
    # `claude -p` obeys the .claude/settings.json of its working directory, which
    # can set ANTHROPIC_BASE_URL and run hooks.
    from datetime import datetime, timezone

    from graphify import prs

    ran_in = tmp_path / "cwds"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    claude = bin_dir / "claude"
    claude.write_text(
        f"#!/bin/sh\n[ \"$1\" = --help ] && exit 0\ncat >/dev/null\npwd -P >>'{ran_in}'\n"
        "echo '{\"type\":\"result\",\"result\":\"{}\"}'\n",
        encoding="utf-8",
    )
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    project = _project(tmp_path, "")
    monkeypatch.chdir(project)
    pr = prs.PRInfo(1, "t", "b", "main", "a", False, "", "SUCCESS", datetime.now(timezone.utc))

    llm._call_claude_cli("source text")
    llm._call_llm("name these", backend="claude-cli", max_tokens=10)
    prs.triage_with_opus([pr], "main", "claude-cli")

    cwds = [Path(line) for line in ran_in.read_text(encoding="utf-8").splitlines()]
    assert len(cwds) == 3
    assert not [d for d in cwds if d.is_relative_to(project.resolve())]


@pytest.mark.parametrize("backend", ["deepseek", "bedrock"])
def test_triage_refuses_a_backend_it_cannot_call(backend: str) -> None:
    from graphify.prs import _resolve_triage_backend

    with pytest.raises(ValueError, match="claude-cli"):
        _resolve_triage_backend(backend)


def _shim(path: Path, log: Path, tag: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"#!/bin/sh\nprintf '%s|%s|%s\\n' '{tag}' \"$(pwd -P)\" \"$*\" >>'{log}'\n"
        "[ \"$1\" = --help ] && exit 0\ncat >/dev/null\n"
        "echo '{\"type\":\"result\",\"result\":\"{}\"}'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX claude shim")
def test_every_claude_launch_is_isolated_from_project_files(monkeypatch, tmp_path: Path) -> None:
    # The working directory is not enough: --add-dir loads a project's skills and
    # agents, and the CLI reads .mcp.json from the parents of its directory (a
    # shared /tmp), unless only the user's own settings sources are loaded.
    from datetime import datetime, timezone

    from graphify import prs

    log = tmp_path / "log"
    project = _project(tmp_path, "")
    _shim(tmp_path / "bin" / "claude", log, "real")
    _shim(project / "claude", log, "planted")
    # A relative PATH entry must not resolve into the project, probe included.
    monkeypatch.setenv(
        "PATH", os.pathsep.join([".", str(tmp_path / "bin"), os.environ["PATH"]])
    )
    monkeypatch.chdir(project)
    monkeypatch.setattr(llm, "_JSON_SCHEMA_SUPPORT", {})
    pr = prs.PRInfo(1, "t", "b", "main", "a", False, "", "SUCCESS", datetime.now(timezone.utc))
    image = llm._ImageRef(project / "pic.png", "pic.png", "image/png", None)

    llm._call_claude_cli("source text", images=[image])
    llm._call_llm("name these", backend="claude-cli", max_tokens=10)
    prs.triage_with_opus([pr], "main", "claude-cli")

    calls = [line.split("|", 2) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [tag for tag, _, _ in calls] == ["real"] * 4
    assert not [d for _, d, _ in calls if Path(d).is_relative_to(project.resolve())]
    requests = [argv for _, _, argv in calls if argv != "--help"]
    assert len(requests) == 3
    for argv in requests:
        assert "--setting-sources user --strict-mcp-config" in argv


def test_windows_refuses_a_claude_found_in_the_current_directory(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    # Windows searches the current directory first, so a project can ship claude.cmd.
    import platform
    import shutil
    import subprocess
    from datetime import datetime, timezone

    from graphify import prs

    monkeypatch.chdir(tmp_path)
    launched: list = []
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: os.path.join(".", "claude.cmd"))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: launched.append(a))
    pr = prs.PRInfo(1, "t", "b", "main", "a", False, "", "SUCCESS", datetime.now(timezone.utc))

    with pytest.raises(RuntimeError, match="current directory"):
        llm._call_claude_cli("source text")
    with pytest.raises(RuntimeError, match="current directory"):
        llm._call_llm("name these", backend="claude-cli", max_tokens=10)
    prs.triage_with_opus([pr], "main", "claude-cli")

    assert "current directory" in capsys.readouterr().err
    assert not launched


def test_claude_cli_directory_is_recreated_when_removed() -> None:
    # A /tmp cleaner may remove it under a long-running process.
    first = llm._claude_cli_cwd()
    os.rmdir(first)
    second = llm._claude_cli_cwd()
    assert os.path.isdir(second) and not os.listdir(second)
