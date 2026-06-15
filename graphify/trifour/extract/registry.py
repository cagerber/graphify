"""Resolve consumer-configured extractors from ``[tool.graphify]``."""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from graphify.config import ExtractorRule, load_graphify_config, match_glob

__all__ = [
    "resolve_consumer_extractor",
    "resolve_consumer_extractors",
]


def _repo_relative(path: Path, project_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return None


def _find_project_root(start: Path) -> Path | None:
    for parent in [start.resolve(), *start.resolve().parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    return None


@lru_cache(maxsize=8)
def _load_callable(module: str, function: str) -> Callable[[Path], dict[str, Any]]:
    mod = importlib.import_module(module)
    fn = getattr(mod, function, None)
    if fn is None or not callable(fn):
        raise ImportError(f"extractor {module}:{function} is not callable")
    return fn


def _matching_extractor_rules(
    path: Path,
    *,
    project_root: Path | None = None,
) -> list[ExtractorRule]:
    """Return all configured extractor rules matching *path* (in declaration order)."""
    root = project_root or _find_project_root(path) or _find_project_root(Path.cwd())
    if root is None:
        return []

    rel = _repo_relative(path, root)
    if rel is None:
        return []

    cfg = load_graphify_config(root)
    suffix = path.suffix.lower()
    matched: list[ExtractorRule] = []
    for rule in cfg.extractors:
        if suffix not in rule.extensions:
            continue
        if rule.path_glob and not match_glob(rel, rule.path_glob):
            continue
        matched.append(rule)
    return matched


def resolve_consumer_extractors(
    path: Path,
    *,
    project_root: Path | None = None,
) -> list[Callable[[Path], dict[str, Any]]]:
    """
    Return every configured extractor matching *path* (multi-extractor merge).

    Rules come from ``[[tool.graphify.extractors]]`` in the consumer ``pyproject.toml``.
    """
    return [
        _load_callable(rule.module, rule.function)
        for rule in _matching_extractor_rules(path, project_root=project_root)
    ]


def resolve_consumer_extractor(
    path: Path,
    *,
    project_root: Path | None = None,
) -> Callable[[Path], dict[str, Any]] | None:
    """
    Return the first configured extractor matching *path*, or ``None``.

    Prefer :func:`resolve_consumer_extractors` when multiple rules may apply.
    """
    extractors = resolve_consumer_extractors(path, project_root=project_root)
    return extractors[0] if extractors else None
