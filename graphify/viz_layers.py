"""Visualization layers: aggregated HTML and test-file hub views."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from graphify.enrich import community_folder_affinity
from graphify.node_paths import is_file_hub_node, normalize_source_path


def _load_labels(out: Path) -> dict[int, str] | None:
    labels_path = out / ".graphify_labels.json"
    if not labels_path.is_file():
        return None
    raw = json.loads(labels_path.read_text(encoding="utf-8"))
    return {int(k): str(v) for k, v in raw.items()}


def communities_from_nodes(nodes: list[dict]) -> dict[int, list[str]]:
    communities: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        cid = node.get("community")
        node_id = node.get("id")
        if cid is None or node_id is None:
            continue
        communities[int(cid)].append(str(node_id))
    return dict(communities)


def _structural_cross_pairs(
    graph: nx.Graph,
    node_to_community: dict[str, int],
) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for u, v in graph.edges():
        cu, cv = node_to_community.get(u), node_to_community.get(v)
        if cu is None or cv is None or cu == cv:
            continue
        pairs.add((min(cu, cv), max(cu, cv)))
    return pairs


def write_aggregated_html(
    graph: nx.Graph,
    communities: dict[int, list[str]],
    nodes: list[dict],
    html_path: Path,
    labels: dict[int, str] | None,
    *,
    folder_affinity: bool = True,
) -> None:
    from graphify.export import to_html

    node_to_community = {
        nid: cid for cid, members in communities.items() for nid in members
    }
    meta = nx.Graph()
    for cid, members in communities.items():
        meta.add_node(
            str(cid),
            label=(labels or {}).get(cid, f"Community {cid}"),
        )

    edge_counts: Counter[tuple[int, int]] = Counter()
    for u, v in graph.edges():
        cu, cv = node_to_community.get(u), node_to_community.get(v)
        if cu is not None and cv is not None and cu != cv:
            edge_counts[(min(cu, cv), max(cu, cv))] += 1

    structural_cross = set(edge_counts.keys())
    for (cu, cv), weight in edge_counts.items():
        meta.add_edge(
            str(cu),
            str(cv),
            weight=weight,
            relation=f"{weight} cross-community edges",
            confidence="AGGREGATED",
        )

    if (
        folder_affinity
        and os.environ.get("GRAPHIFY_FOLDER_AFFINITY", "1") != "0"
    ):
        for cu, cv, relation, weight in community_folder_affinity(
            nodes, structural_cross
        ):
            if meta.has_edge(str(cu), str(cv)):
                continue
            meta.add_edge(
                str(cu),
                str(cv),
                weight=weight,
                relation=relation,
                confidence="INFERRED",
            )

    if meta.number_of_nodes() <= 1:
        print("Single community; skipping aggregated HTML.")
        return

    meta_communities = {cid: [str(cid)] for cid in communities}
    member_counts = {cid: len(members) for cid, members in communities.items()}

    raw_hyperedges = graph.graph.get("hyperedges", [])
    if raw_hyperedges:
        remapped = []
        for he in raw_hyperedges:
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
        meta.graph["hyperedges"] = remapped

    to_html(
        meta,
        meta_communities,
        str(html_path),
        community_labels=labels,
        member_counts=member_counts,
    )


def emit_default_html(out_dir: Path, *, project_root: Path | None = None) -> bool:
    """Write graph.html (aggregated when over viz limit)."""
    from graphify.export import _viz_node_limit, to_html

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


def emit_test_files_html(
    out_dir: Path,
    output_path: Path | None = None,
    *,
    test_roots: list[str] | None = None,
) -> bool:
    from graphify.config import load_graphify_config
    from graphify.export import to_html

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
