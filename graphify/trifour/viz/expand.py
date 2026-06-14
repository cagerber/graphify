"""Community expansion (single + neighborhood) with node budget."""

from __future__ import annotations

from collections import deque
from typing import Any

from graphify.trifour.viz.aggregate import build_meta_edge_counts, graph_from_document
from graphify.trifour.viz.communities import communities_from_nodes
from graphify.viz_contract import GraphDocument


class ExpansionBudgetError(ValueError):
    def __init__(self, projected: int, limit: int) -> None:
        super().__init__(
            f"expansion would include {projected} nodes (limit {limit}); "
            "narrow selection or lower neighborhoodHop"
        )
        self.projected = projected
        self.limit = limit


def _community_neighbors(
    focus_ids: list[int],
    meta_adj: dict[int, set[int]],
    hop: int,
) -> set[int]:
    visited: set[int] = set(int(c) for c in focus_ids)
    queue: deque[tuple[int, int]] = deque((int(c), 0) for c in focus_ids)
    while queue:
        cid, depth = queue.popleft()
        if depth >= hop:
            continue
        for nb in meta_adj.get(cid, ()):
            if nb in visited:
                continue
            visited.add(nb)
            queue.append((nb, depth + 1))
    return visited


def apply_expansion(
    doc: GraphDocument,
    *,
    view_mode: str,
    focus_community_ids: list[int] | None = None,
    expansion_mode: str = "neighborhood",
    neighborhood_hop: int = 1,
    max_nodes: int = 800,
) -> GraphDocument:
    """Transform document per view_mode; fail fast when over budget."""
    mode = (view_mode or "full").strip()
    if mode in ("full", "test_file_hubs"):
        return doc
    if mode == "aggregated_communities":
        from graphify.trifour.viz.aggregate import build_aggregated_document

        return build_aggregated_document(doc)

    if mode != "expanded_communities":
        raise ValueError(f"unknown viewMode: {mode}")

    focus = [int(c) for c in (focus_community_ids or [])]
    if not focus:
        raise ValueError("focusCommunityIds required for expanded_communities view")

    communities = communities_from_nodes(doc["nodes"])
    graph = graph_from_document(doc)
    node_to_community = {
        nid: cid for cid, members in communities.items() for nid in members
    }
    edge_counts = build_meta_edge_counts(graph, node_to_community)
    meta_adj: dict[int, set[int]] = {}
    for cu, cv in edge_counts:
        meta_adj.setdefault(cu, set()).add(cv)
        meta_adj.setdefault(cv, set()).add(cu)

    if expansion_mode == "single":
        allowed_communities = set(focus)
    elif expansion_mode == "neighborhood":
        allowed_communities = _community_neighbors(
            focus, meta_adj, max(0, neighborhood_hop)
        )
    else:
        raise ValueError(f"unknown expansionMode: {expansion_mode}")

    allowed_nodes: set[str] = set()
    for cid in allowed_communities:
        for nid in communities.get(cid, ()):
            allowed_nodes.add(nid)

    if len(allowed_nodes) > max_nodes:
        raise ExpansionBudgetError(len(allowed_nodes), max_nodes)

    node_by_id = {str(n["id"]): n for n in doc["nodes"] if n.get("id")}
    out_nodes = [node_by_id[nid] for nid in sorted(allowed_nodes) if nid in node_by_id]
    out_edges: list[dict[str, Any]] = []
    for edge in doc["edges"]:
        src, tgt = edge.get("source"), edge.get("target")
        if src in allowed_nodes and tgt in allowed_nodes:
            out_edges.append(edge)

    meta = dict(doc["meta"])
    meta["viewMode"] = "expanded_communities"
    meta["focusCommunityIds"] = sorted(allowed_communities)
    meta["expansionMode"] = expansion_mode
    meta["neighborhoodHop"] = neighborhood_hop
    return GraphDocument(meta=meta, nodes=out_nodes, edges=out_edges)
