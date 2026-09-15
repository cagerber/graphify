"""Load graph.json and sidecars into a GraphDocument."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graphify.viz_contract import GraphDocument


def _load_labels(out: Path) -> dict[int, str]:
    labels_path = out / ".graphify_labels.json"
    if not labels_path.is_file():
        return {}
    raw = json.loads(labels_path.read_text(encoding="utf-8"))
    return {int(k): str(v) for k, v in raw.items()}


def _load_manifest(out: Path) -> dict[str, Any]:
    manifest_path = out / "manifest.json"
    if not manifest_path.is_file():
        return {}
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def load_document(graph_path: Path, *, out_dir: Path | None = None) -> GraphDocument:
    """Load graph.json; fail fast if missing or invalid."""
    path = Path(graph_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"graph.json not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"graph.json root must be an object: {path}")

    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError(f"graph.json missing nodes array: {path}")

    edges_raw = data.get("links")
    if edges_raw is None:
        edges_raw = data.get("edges")
    if not isinstance(edges_raw, list):
        edges_raw = []

    edges: list[dict[str, Any]] = [e for e in edges_raw if isinstance(e, dict)]
    out = out_dir if out_dir is not None else path.parent

    labels = _load_labels(out)
    manifest = _load_manifest(out)
    node_count = len(nodes)
    limit_raw = __import__("os").environ.get("GRAPHIFY_VIZ_NODE_LIMIT", "500")
    try:
        viz_limit = int(limit_raw)
    except ValueError:
        viz_limit = 500

    meta: dict[str, Any] = {
        "documentType": "graphify",
        "graphPath": str(path),
        "nodeCount": node_count,
        "edgeCount": len(edges),
        "communityLabels": {str(k): v for k, v in sorted(labels.items())},
        "manifest": manifest,
    }
    if viz_limit > 0 and node_count > viz_limit:
        meta["recommendedViewMode"] = "aggregated_communities"
        meta["vizNodeLimit"] = viz_limit
    else:
        meta["recommendedViewMode"] = "full"

    hyperedges = data.get("hyperedges")
    if hyperedges:
        meta["hyperedges"] = hyperedges

    return GraphDocument(meta=meta, nodes=nodes, edges=edges)
