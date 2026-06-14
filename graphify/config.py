"""Load ``[tool.graphify]`` from consumer ``pyproject.toml`` (no hardcoded repo paths)."""

from __future__ import annotations

import fnmatch
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TestsCoversRule:
    """Map test file globs to production paths via explicit strip rules."""

    test: str
    strip_prefix: str = "tests/"
    strip_test_filename_prefix: str = "test_"
    collapse_tests_dir: bool = False


@dataclass
class GraphifyConfig:
    test_roots: list[str] = field(default_factory=lambda: ["tests"])
    tests_covers: list[TestsCoversRule] = field(default_factory=list)
    folder_prefix_depth: int = 2
    folder_edges: bool = True
    folder_affinity: bool = True
    pytest_enrich: bool = True
    heuristic_labels: bool = False


def _env_bool(name: str, default: bool) -> bool:
    """Resolve a boolean from env when set; otherwise use *default*."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() not in ("0", "false", "no", "off")


def enrich_flags(project_root: Path | str | None = None) -> dict[str, bool]:
    """Merge ``[tool.graphify]`` enrich defaults with ``GRAPHIFY_*`` env overrides."""
    cfg = load_graphify_config(project_root)
    return {
        "folder_edges": _env_bool("GRAPHIFY_FOLDER_EDGES", cfg.folder_edges),
        "folder_affinity": _env_bool("GRAPHIFY_FOLDER_AFFINITY", cfg.folder_affinity),
        "pytest_enrich": _env_bool("GRAPHIFY_PYTEST_ENRICH", cfg.pytest_enrich),
        "heuristic_labels": _env_bool("GRAPHIFY_HEURISTIC_LABELS", cfg.heuristic_labels),
    }


def _find_pyproject(root: Path) -> Path | None:
    for parent in [root, *root.parents]:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def load_graphify_config(root: Path | str | None = None) -> GraphifyConfig:
    """Load ``[tool.graphify]`` from the nearest ``pyproject.toml`` upward from *root*."""
    base = Path(root or ".").resolve()
    pyproject = _find_pyproject(base)
    if pyproject is None:
        return GraphifyConfig()

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return GraphifyConfig()

    section: dict[str, Any] = data.get("tool", {}).get("graphify", {})
    if not section:
        return GraphifyConfig()

    rules: list[TestsCoversRule] = []
    for item in section.get("tests_covers", []):
        if not isinstance(item, dict):
            continue
        test_pat = item.get("test")
        if not test_pat:
            continue
        rules.append(
            TestsCoversRule(
                test=str(test_pat),
                strip_prefix=str(item.get("strip_prefix", "tests/")),
                strip_test_filename_prefix=str(
                    item.get("strip_test_filename_prefix", "test_")
                ),
                collapse_tests_dir=bool(item.get("collapse_tests_dir", False)),
            )
        )

    test_roots = section.get("test_roots", ["tests"])
    if isinstance(test_roots, str):
        test_roots = [test_roots]

    depth = section.get("folder_prefix_depth", 2)
    try:
        folder_prefix_depth = int(depth)
    except (TypeError, ValueError):
        folder_prefix_depth = 2

    return GraphifyConfig(
        test_roots=[str(r) for r in test_roots],
        tests_covers=rules,
        folder_prefix_depth=folder_prefix_depth,
        folder_edges=bool(section.get("folder_edges", True)),
        folder_affinity=bool(section.get("folder_affinity", True)),
        pytest_enrich=bool(section.get("pytest_enrich", True)),
        heuristic_labels=bool(section.get("heuristic_labels", False)),
    )


def match_glob(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return fnmatch.fnmatch(normalized, pattern)


def production_path_for_test(test_path: str, rule: TestsCoversRule) -> str | None:
    """Return production path when *test_path* matches *rule.test*; else None."""
    normalized = test_path.replace("\\", "/").lstrip("./")
    if not match_glob(normalized, rule.test):
        return None
    rel = normalized
    if rule.collapse_tests_dir:
        rel = rel.replace("/tests/", "/", 1)
    if rule.strip_prefix and rel.startswith(rule.strip_prefix):
        rel = rel[len(rule.strip_prefix) :].lstrip("/")
    path = Path(rel)
    name = path.name
    if name.startswith("test_") and name.endswith(".py"):
        name = name[5:]
    elif rule.strip_test_filename_prefix and name.startswith(rule.strip_test_filename_prefix):
        name = name[len(rule.strip_test_filename_prefix) :]
    if path.parent != Path("."):
        return str(path.parent / name).replace("\\", "/")
    return name
