"""Resolve a consumer's fully qualified symbol name (``node_ref``) to its node.

One symbol often has several nodes carrying the same ``node_ref``: the node that
declares it, plus other views of it (an inventory entry, a data-model mapping).
The declaring node is told apart by structure, never by a consumer's node kinds:
it owns members, or is itself a member, or the other views hang off it.
"""
from __future__ import annotations

from typing import Iterator

import networkx as nx

__all__ = ["node_ref_matches", "same_symbol"]

_OWNER_RELATIONS = ("method", "contains")
_MEMBER_SUFFIX = ".member_of"


def _index(G: nx.Graph) -> dict[str, list[str]]:
    index = G.graph.get("_node_ref_index")
    if index is None:
        index = {}
        for nid, d in G.nodes(data=True):
            if d.get("node_ref"):
                index.setdefault(str(d["node_ref"]).lower(), []).append(nid)
        G.graph["_node_ref_index"] = index
    return index


def _edges(G: nx.Graph, nid: str, *, out: bool) -> Iterator[tuple[str, str]]:
    """``(neighbour, relation)`` for the stored direction of *nid*'s edges."""
    if G.is_directed():
        pairs = (
            ((t, d) for _, t, d in G.out_edges(nid, data=True))
            if out
            else ((s, d) for s, _, d in G.in_edges(nid, data=True))
        )
    else:
        pairs = (
            (n, d)
            for _, n, d in G.edges(nid, data=True)
            if (d.get("_src", nid) == nid) is out
        )
    for neighbour, data in pairs:
        yield neighbour, str(data.get("relation", ""))


def _owns_members(G: nx.Graph, nid: str) -> bool:
    return any(r.endswith(_MEMBER_SUFFIX) for _, r in _edges(G, nid, out=False)) or any(
        r in _OWNER_RELATIONS for _, r in _edges(G, nid, out=True)
    )


def _is_member(G: nx.Graph, nid: str) -> bool:
    return any(r.endswith(_MEMBER_SUFFIX) for _, r in _edges(G, nid, out=True))


def _is_root(G: nx.Graph, nid: str, group: set[str]) -> bool:
    """Other views of the symbol are linked from this one, and none links to it."""
    return any(n in group and n != nid for n, _ in _edges(G, nid, out=True)) and not any(
        n in group and n != nid for n, _ in _edges(G, nid, out=False)
    )


def _declaring(G: nx.Graph, hits: list[str], name: str) -> list[str]:
    """The nodes among *hits* that declare the symbol; several means ambiguous."""
    if len(hits) < 2:
        return list(hits)
    pool = [n for n in hits if not G.nodes[n].get("ref_stub")] or list(hits)
    group = set(pool)
    found = (
        [n for n in pool if _owns_members(G, n)]
        or [n for n in pool if _is_member(G, n)]
        or [n for n in pool if _is_root(G, n, group)]
        # A reference stub's concept node must not make a definition ambiguous.
        or [n for n in pool if G.nodes[n].get("file_type") != "concept"]
        or pool
    )
    # Names that differ only in case are different symbols in some languages.
    same_case = [n for n in found if str(G.nodes[n].get("node_ref")) == name]
    return same_case if len(same_case) == 1 else found


def node_ref_matches(G: nx.Graph, label: str) -> list[str]:
    """The declaring node(s) of the symbol whose ``node_ref`` is *label*.

    Empty when no node carries that name; one id when it is unambiguous.
    """
    name = label.strip().removesuffix("()")
    return _declaring(G, _index(G).get(name.lower(), []), name)


def same_symbol(G: nx.Graph, nid: str) -> list[str]:
    """The other nodes that stand for the same symbol as *nid*, in the same repo.

    Empty unless exactly one node declares that symbol and *nid* is it or one of
    its views. A same-named member (a property named like a class) is another
    symbol and is never included.
    """
    data = G.nodes[nid]
    name = str(data.get("node_ref") or "")
    if not name:
        return []
    repo = data.get("repo")
    group = [n for n in _index(G).get(name.lower(), []) if G.nodes[n].get("repo") == repo]
    if len(group) < 2:
        return []
    declaring = _declaring(G, group, name)
    if len(declaring) != 1:
        return []
    symbol = [
        n for n in group
        if n == declaring[0] or not (_owns_members(G, n) or _is_member(G, n))
    ]
    return [n for n in symbol if n != nid] if nid in symbol else []
