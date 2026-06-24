"""Canonical graphify output paths (GRAPHIFY_OUT env).

All runtime resolution goes through here so import-time defaults do not
freeze ``graphify-out/`` when the env var is set later (e.g. ODS
``.local/graphify-out``).

Upstream #1423 symbols (``GRAPHIFY_OUT``, ``GRAPHIFY_OUT_NAME``, ``out_path``,
``default_graph_json``) are exposed via :func:`graphify_out_rel` and PEP 562
lazy attributes so env overrides remain call-time safe.
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_REL = "graphify-out"


def graphify_out_rel() -> str:
    """Relative or absolute output directory from GRAPHIFY_OUT (default graphify-out)."""
    return os.environ.get("GRAPHIFY_OUT", _DEFAULT_REL)


def graphify_out_name() -> str:
    """Bare directory name even when GRAPHIFY_OUT is an absolute path."""
    return os.path.basename(os.path.normpath(graphify_out_rel()))


def graphify_out_dir(root: Path | str | None = None) -> Path:
    """Resolved output directory under *root* (or cwd when *root* is None)."""
    rel = graphify_out_rel()
    out = Path(rel)
    if out.is_absolute():
        return out
    base = Path(root).resolve() if root is not None else Path.cwd()
    return base / rel


def graphify_project_root(watch_path: Path | str | None = None) -> Path:
    """Repository root for resolving relative ``GRAPHIFY_OUT`` during subpath scans.

    When ``graphify update reference/`` runs from the repo root, output must land
    in ``<repo>/.local/graphify-out``, not ``reference/.local/graphify-out``.
    """
    if watch_path is None:
        return Path.cwd().resolve()
    wp = Path(watch_path)
    if wp.is_absolute():
        return wp.resolve()
    return Path.cwd().resolve()


def graphify_out_for_watch(watch_path: Path | str | None = None) -> Path:
    """``GRAPHIFY_OUT`` anchored at :func:`graphify_project_root`, not the watch subfolder."""
    return graphify_out_dir(graphify_project_root(watch_path))


def out_path(*parts: str, root: Path | str | None = None) -> Path:
    """A path inside the configured output dir, e.g. ``out_path("cache")``."""
    return graphify_out_dir(root).joinpath(*parts)


def manifest_path(root: Path | str | None = None) -> str:
    return str(graphify_out_dir(root) / "manifest.json")


def default_graph_json_path(root: Path | str | None = None) -> str:
    return str(graphify_out_dir(root) / "graph.json")


def default_graph_json(root: Path | str | None = None) -> str:
    """Upstream alias for :func:`default_graph_json_path`."""
    return default_graph_json_path(root)


def skip_dir_names() -> frozenset[str]:
    """Directory basename(s) to skip when scanning source (includes GRAPHIFY_OUT tail)."""
    names = {_DEFAULT_REL}
    rel = graphify_out_rel()
    for part in Path(rel).parts:
        if part not in (".", ".."):
            names.add(part)
    return frozenset(names)


def __getattr__(name: str) -> object:
    if name == "GRAPHIFY_OUT":
        return graphify_out_rel()
    if name == "GRAPHIFY_OUT_NAME":
        return graphify_out_name()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
