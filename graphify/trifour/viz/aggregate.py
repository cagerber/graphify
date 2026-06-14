"""Community meta-graph aggregation."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from graphify.config import enrich_flags
from graphify.enrich import community_folder_affinity
from graphify.trifour.viz.communities import communities_from_nodes
from graphify.viz_contract import GraphDocument


def node_to_community_map(nodes: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for node in nodes:
        cid = node.get("community")
        nid = node.get("id")
        if cid is None or nid is None:
            continue
        out[str(nid)] = int(cid)
    return out


def build_meta_edge_counts(
    graph: nx.Graph,
    node_to_community: dict[str, int],
) -> Counter[tuple[int, int]]:
    edge_counts: Counter[tuple[int, int]] = Counter()
    for u, v in graph.edges():
        cu, cv = node_to_community.get(u), node_to_community.get(v)
        if cu is not None and cv is not None and cu != cv:
            edge_counts[(min(cu, cv), max(cu, cv))] += 1
    return edge_counts


def build_aggregated_document(
    doc: GraphDocument,
    *,
    labels: dict[int, str] | None = None,
    folder_affinity: bool = True,
) -> GraphDocument:
    """Collapse member nodes into community meta-nodes."""
    nodes = doc["nodes"]
    edges = doc["edges"]
    communities = communities_from_nodes(nodes)
    if len(communities) <= 1:
        return doc

    label_map = labels or {}
    if not label_map:
        raw = doc["meta"].get("communityLabels") or {}
        label_map = {int(k): str(v) for k, v in raw.items()}

    node_to_community = node_to_community_map(nodes)
    graph = nx.Graph()
    for node in nodes:
        nid = node.get("id")
        if nid is None:
            continue
        graph.add_node(str(nid))

    for edge in edges:
        src, tgt = edge.get("source"), edge.get("target")
        if src is None or tgt is None:
            continue
        graph.add_edge(
            str(src),
            str(tgt),
            relation=edge.get("relation", ""),
            confidence=edge.get("confidence", "EXTRACTED"),
        )

    edge_counts = build_meta_edge_counts(graph, node_to_community)
    structural_cross = set(edge_counts.keys())

    meta_nodes: list[dict[str, Any]] = []
    for cid in sorted(communities):
        members = communities[cid]
        meta_nodes.append(
            {
                "id": str(cid),
                "label": label_map.get(cid, f"Community {cid}"),
                "kind": "community",
                "community": cid,
                "member_count": len(members),
                "member_ids": members,
            }
        )

    meta_edges: list[dict[str, Any]] = []
    for (cu, cv), weight in edge_counts.items():
        meta_edges.append(
            {
                "source": str(cu),
                "target": str(cv),
                "relation": f"{weight} cross-community edges",
                "confidence": "AGGREGATED",
                "weight": weight,
            }
        )

    if folder_affinity and enrich_flags().get("folder_affinity", True):
        existing = {(e["source"], e["target"]) for e in meta_edges}
        for cu, cv, relation, weight in community_folder_affinity(
            nodes, structural_cross
        ):
            src, tgt = str(cu), str(cv)
            if (src, tgt) in existing or (tgt, src) in existing:
                continue
            meta_edges.append(
                {
                    "source": src,
                    "target": tgt,
                    "relation": relation,
                    "confidence": "INFERRED",
                    "weight": weight,
                }
            )
            existing.add((src, tgt))

    meta = dict(doc["meta"])
    meta["viewMode"] = "aggregated_communities"
    meta["aggregated"] = True
    return GraphDocument(meta=meta, nodes=meta_nodes, edges=meta_edges)


def graph_from_document(doc: GraphDocument) -> nx.Graph:
    data = {
        "nodes": doc["nodes"],
        "links": doc["edges"],
    }
    try:
        return json_graph.node_link_graph(data, edges="links")
    except TypeError:
        return json_graph.node_link_graph(data)
