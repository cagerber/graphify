"""Fold consumer reference stubs into the node that defines the symbol.

A consumer extractor sees one file at a time, so a call into another file needs a
placeholder node carrying the callee's id. It marks that node ``ref_stub``. Left
in place, the placeholder and the definition are one id from two files, which the
id disambiguation splits apart, so no cross-file edge reaches the definition.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

__all__ = ["carry_referenced_stubs", "drop_superseded_stubs", "fold_ref_stubs"]


def fold_ref_stubs(nodes: list[dict], context_nodes: Iterable[dict] = ()) -> None:
    """Drop redundant ``ref_stub`` nodes from *nodes* in place.

    One definition (in *nodes* or the unchanged *context_nodes*): its stubs go and
    every edge keeps the shared id. No definition: one stub stays, none if
    *context_nodes* already hold one. Definitions in several files: stubs stay, so
    disambiguation treats them as before.
    """
    context_nodes = list(context_nodes)
    definers: dict[str, set[str]] = {}
    for node in [*nodes, *context_nodes]:
        if not node.get("ref_stub"):
            definers.setdefault(str(node.get("id")), set()).add(str(node.get("source_file", "")))

    kept: list[dict] = []
    stubbed = {str(n.get("id")) for n in context_nodes if n.get("ref_stub")}
    for node in nodes:
        if node.get("ref_stub"):
            nid = str(node.get("id"))
            homes = len(definers.get(nid, ()))
            if homes == 1 or (homes == 0 and nid in stubbed):
                continue
            stubbed.add(nid)
        kept.append(node)
    nodes[:] = kept


def drop_superseded_stubs(existing: list[dict], chunks: Iterable[dict]) -> list[dict]:
    """*existing* without the persisted stubs a fresh definition replaces.

    A merge keeps the saved copy of an id it already holds, which would leave the
    stub standing where the definition now is.
    """
    defined = {
        node.get("id")
        for chunk in chunks
        for node in chunk.get("nodes", [])
        if not node.get("ref_stub")
    }
    return [n for n in existing if not (n.get("ref_stub") and n.get("id") in defined)]


def carry_referenced_stubs(
    dropped: Iterable[dict],
    surviving_edges: Iterable[dict],
    fresh_ids: set,
    root: str | Path,
) -> list[dict]:
    """Stubs for the saved nodes an incremental merge drops but others still use.

    Folding leaves one node per symbol, hosted in one file. When that file stops
    emitting it (call or definition removed, file deleted), the other files'
    edges would go with it. Each such node is kept as a stub of one of the files
    that use it; no file is read again. Only nodes and edges of consumer-extractor
    files take part.
    """
    from graphify.ext.extract.registry import resolve_consumer_extractors

    @lru_cache(maxsize=None)  # a graph repeats each source_file many times
    def owned(source_file: str) -> bool:
        return bool(resolve_consumer_extractors(Path(root) / source_file))

    lost = {
        n.get("id"): n
        for n in dropped
        if n.get("id") not in fresh_ids
        and n.get("source_file")
        and owned(n["source_file"])
    }
    users: dict[str, str] = {}
    for edge in surviving_edges:
        source_file = edge.get("source_file")
        if not source_file:
            continue
        for nid in (edge.get("source"), edge.get("target")):
            if nid in lost and owned(source_file):
                users[nid] = min(source_file, users.get(nid, source_file))

    carried = []
    for nid, source_file in users.items():
        node = lost[nid]
        if not node.get("ref_stub"):  # a removed definition keeps only its identity
            keys = ("id", "label", "file_type", "node_ref", "_origin")
            node = {key: node[key] for key in keys if key in node}
        node = {**node, "source_file": source_file, "ref_stub": True}
        node.pop("source_location", None)
        carried.append(node)
    return carried
