"""Post-extract merge for ODS consumer KG extensions (extended product pass)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _ensure_consumer_tools_on_path(project_root: Path) -> bool:
    """Insert ``<repo>/tools`` on ``sys.path`` when *project_root* is inside a consumer checkout."""
    for parent in [project_root.resolve(), *project_root.resolve().parents]:
        tools = parent / "tools"
        marker = parent / "pyproject.toml"
        if tools.is_dir() and marker.is_file():
            entry = str(tools.resolve())
            if entry not in sys.path:
                sys.path.insert(0, entry)
            return True
    return False


def merge_consumer_kg_extensions(
    result: dict[str, Any],
    *,
    project_root: Path,
    full_rebuild: bool,
) -> dict[str, Any]:
    """
    On full corpus rebuild, merge extended BI product artefact nodes/edges.

    Incremental rebuilds leave extended artefacts untouched (refreshed on next
    full ``graphify update .``). No-op when *project_root* is not an ODS-style
    consumer (no ``tools/`` + ``pyproject.toml`` walk-up).
    """
    if not full_rebuild:
        return result

    if not _ensure_consumer_tools_on_path(project_root):
        return result

    try:
        from shared.kg_extract.emit_extended import (
            build_extended_product_fragment,
            strip_extended_artefacts_from_result,
        )
    except ImportError:
        # Non-ODS consumers may have a tools/ tree without this package.
        return result

    strip_extended_artefacts_from_result(result)
    frag = build_extended_product_fragment(project_root)
    if frag.errors:
        raise ValueError(frag.errors[0])

    ext = frag.to_graphify_dict()
    if ext.get("error"):
        raise ValueError(str(ext["error"]))

    existing_ids = {n.get("id") for n in result.get("nodes", [])}
    for node in ext.get("nodes", []):
        nid = node.get("id")
        if nid and nid not in existing_ids:
            result.setdefault("nodes", []).append(node)
            existing_ids.add(nid)

    edge_key = "edges" if "edges" in result else "links"
    seen_edges = {
        (e.get("source"), e.get("target"), e.get("relation"))
        for e in result.get(edge_key, [])
    }
    for edge in ext.get("edges", []):
        key = (edge.get("source"), edge.get("target"), edge.get("relation"))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        result.setdefault(edge_key, []).append(edge)

    return result
