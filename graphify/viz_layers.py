"""Visualization layers: aggregated HTML and test-file hub views."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from graphify.exporters.html import _viz_node_limit, to_html
from graphify.trifour.viz.aggregate import build_aggregated_document, graph_from_document
from graphify.trifour.viz.communities import communities_from_nodes
from graphify.trifour.viz.load import load_document
from graphify.trifour.viz.test_hubs import build_test_file_hub_graph

__all__ = [
    "communities_from_nodes",
    "build_test_file_hub_graph",
    "write_aggregated_html",
    "emit_default_html",
    "emit_test_files_html",
]


def _load_labels(out: Path) -> dict[int, str] | None:
    labels_path = out / ".graphify_labels.json"
    if not labels_path.is_file():
        return None
    raw = json.loads(labels_path.read_text(encoding="utf-8"))
    return {int(k): str(v) for k, v in raw.items()}


def write_aggregated_html(
    graph: nx.Graph,
    communities: dict[int, list[str]],
    nodes: list[dict],
    html_path: Path,
    labels: dict[int, str] | None,
    *,
    folder_affinity: bool = True,
) -> None:
    doc = load_document(html_path.parent / "graph.json")
    agg = build_aggregated_document(
        doc, labels=labels, folder_affinity=folder_affinity
    )
    meta_graph = graph_from_document(agg)
    meta_communities = {int(str(n["community"])): [str(n["id"])] for n in agg["nodes"]}
    member_counts = {
        int(str(n["community"])): int(n.get("member_count") or 0) for n in agg["nodes"]
    }

    hyperedges = doc["meta"].get("hyperedges")
    if hyperedges:
        node_to_community = {
            nid: cid for cid, members in communities.items() for nid in members
        }
        remapped = []
        for he in hyperedges:
            he_members = he.get("nodes") or he.get("members") or []
            comm_ids: list[str] = []
            seen: set[str] = set()
            for nid in he_members:
                comm = node_to_community.get(nid)
                if comm is None:
                    continue
                token = str(comm)
                if token in seen:
                    continue
                seen.add(token)
                comm_ids.append(token)
            if len(comm_ids) < 2:
                continue
            remapped.append(
                {
                    "id": he.get("id", ""),
                    "label": he.get("label")
                    or he.get("relation", "").replace("_", " "),
                    "nodes": comm_ids,
                }
            )
        meta_graph.graph["hyperedges"] = remapped

    if meta_graph.number_of_nodes() <= 1:
        print("Single community; skipping aggregated HTML.")
        return

    to_html(
        meta_graph,
        meta_communities,
        str(html_path),
        community_labels=labels,
        member_counts=member_counts,
    )


def emit_default_html(out_dir: Path, *, project_root: Path | None = None) -> bool:
    """Write graph.html (aggregated when over viz limit)."""
    graph_path = out_dir / "graph.json"
    html_path = out_dir / "graph.html"
    if not graph_path.is_file():
        return False

    limit = _viz_node_limit()
    if limit == 0:
        return False

    data = json.loads(graph_path.read_text(encoding="utf-8"))
    try:
        graph = json_graph.node_link_graph(data, edges="links")
    except TypeError:
        graph = json_graph.node_link_graph(data)
    hyperedges = data.get("hyperedges")
    if hyperedges:
        graph.graph["hyperedges"] = hyperedges

    communities = communities_from_nodes(data.get("nodes", []))
    labels = _load_labels(out_dir)
    node_count = graph.number_of_nodes()
    nodes = data.get("nodes", [])

    if node_count <= limit:
        to_html(graph, communities, str(html_path), community_labels=labels)
        return html_path.is_file()

    write_aggregated_html(
        graph, communities, nodes, html_path, labels, folder_affinity=True
    )
    return html_path.is_file()


def emit_test_files_html(
    out_dir: Path,
    output_path: Path | None = None,
    *,
    test_roots: list[str] | None = None,
) -> bool:
    from graphify.config import load_graphify_config

    graph_path = out_dir / "graph.json"
    if not graph_path.is_file():
        return False

    config = load_graphify_config(out_dir)
    roots = test_roots or config.test_roots
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    graph, communities = build_test_file_hub_graph(data, test_roots=roots)
    if graph.number_of_nodes() == 0:
        print("No test file hubs found; skipping test-files HTML.")
        return False

    labels = _load_labels(out_dir)
    target = output_path or (out_dir / "graph-tests.html")
    to_html(graph, communities, str(target), community_labels=labels)
    print(f"graph-tests.html written ({graph.number_of_nodes()} test file hubs).")
    return target.is_file()
