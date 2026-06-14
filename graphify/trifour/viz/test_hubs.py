"""Test-file hub graph transform."""

from __future__ import annotations

import networkx as nx

from graphify.node_paths import is_file_hub_node, normalize_source_path
from graphify.trifour.viz.communities import communities_from_nodes


def build_test_file_hub_graph(
    data: dict,
    *,
    test_roots: list[str] | None = None,
) -> tuple[nx.Graph, dict[int, list[str]]]:
    """Collapse to file hubs under configured test roots."""
    roots = test_roots or ["tests"]
    nodes = data.get("nodes", [])
    hub_ids: set[str] = set()
    hub_nodes: dict[str, dict] = {}

    for node in nodes:
        sf = normalize_source_path(node.get("source_file") or "")
        if not sf:
            continue
        under_test = any(
            sf == r.rstrip("/") or sf.startswith(r.rstrip("/") + "/") for r in roots
        )
        if not under_test:
            continue
        if node.get("kind") == "file" or is_file_hub_node(node):
            nid = str(node.get("id"))
            if nid:
                hub_ids.add(nid)
                hub_nodes[nid] = node

    allowed_relations = {
        "tests_covers",
        "imports",
        "imports_from",
        "same_directory",
        "shared_folder",
        "calls",
        "contains",
    }
    edges = data.get("links") or data.get("edges") or []

    graph = nx.Graph()
    for nid, node in hub_nodes.items():
        graph.add_node(nid, **{k: v for k, v in node.items() if k != "id"})

    for edge in edges:
        rel = edge.get("relation", "")
        if rel not in allowed_relations and edge.get("confidence") != "INFERRED":
            if not rel.startswith("same_") and rel != "shared_folder":
                continue
        src, tgt = edge.get("source"), edge.get("target")
        if src in hub_ids and tgt in hub_ids:
            graph.add_edge(
                src,
                tgt,
                relation=rel,
                confidence=edge.get("confidence", "EXTRACTED"),
            )

    communities = communities_from_nodes(list(hub_nodes.values()))
    return graph, communities
