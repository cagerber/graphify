"""Canonical graphify output paths (GRAPHIFY_OUT env).

All runtime resolution goes through here so import-time defaults do not
freeze ``graphify-out/`` when the env var is set later (e.g. ODS
``.local/graphify-out``).
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_REL = "graphify-out"


def graphify_out_rel() -> str:
    """Relative or absolute output directory from GRAPHIFY_OUT (default graphify-out)."""
    return os.environ.get("GRAPHIFY_OUT", _DEFAULT_REL)


def graphify_out_dir(root: Path | str | None = None) -> Path:
    """Resolved output directory under *root* (or cwd when *root* is None)."""
    rel = graphify_out_rel()
    out = Path(rel)
    if out.is_absolute():
        return out
    base = Path(root).resolve() if root is not None else Path.cwd()
    return base / rel


def manifest_path(root: Path | str | None = None) -> str:
    return str(graphify_out_dir(root) / "manifest.json")


def default_graph_json_path(root: Path | str | None = None) -> str:
    return str(graphify_out_dir(root) / "graph.json")


def skip_dir_names() -> frozenset[str]:
    """Directory basename(s) to skip when scanning source (includes GRAPHIFY_OUT tail)."""
    names = {_DEFAULT_REL}
    rel = graphify_out_rel()
    for part in Path(rel).parts:
        if part not in (".", ".."):
            names.add(part)
    return frozenset(names)
