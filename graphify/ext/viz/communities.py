"""Community membership helpers."""

from __future__ import annotations

from collections import defaultdict


def communities_from_nodes(nodes: list[dict]) -> dict[int, list[str]]:
    communities: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        cid = node.get("community")
        node_id = node.get("id")
        if cid is None or node_id is None:
            continue
        communities[int(cid)].append(str(node_id))
    return dict(communities)
