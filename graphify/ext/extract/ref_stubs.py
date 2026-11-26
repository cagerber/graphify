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

__all__ = ["drop_superseded_stubs", "fold_ref_stubs", "ref_stub_referrer_paths"]


def fold_ref_stubs(nodes: list[dict], context_nodes: Iterable[dict] = ()) -> None:
    """Drop redundant ``ref_stub`` nodes from *nodes* in place.

    One definition (in *nodes* or the unchanged *context_nodes*): its stubs go and
    every edge keeps the shared id. No definition: one stub stays. Definitions in
    several files: stubs stay, so disambiguation treats them as before.
    """
    definers: dict[str, set[str]] = {}
    for node in [*nodes, *context_nodes]:
        if not node.get("ref_stub"):
            definers.setdefault(str(node.get("id")), set()).add(str(node.get("source_file", "")))

    kept: list[dict] = []
    stubbed: set[str] = set()
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


def ref_stub_referrer_paths(
    paths: list[Path],
    graph: dict,
    root: Path,
    available_paths: list[Path],
    changed_paths: list[Path],
) -> list[Path]:
    """Add to an incremental batch the files that point at a symbol it drops.

    Folding leaves one node per symbol, hosted in one file. When that file stops
    emitting it (call or definition removed, file deleted), the other files'
    edges would go with it; reading those files again gives them a node to point
    at. Only consumer-extractor files host such nodes.
    """
    from graphify.ext.extract.registry import resolve_consumer_extractors
    from graphify.extractors.resolution import _cpp_source_key

    @lru_cache(maxsize=None)  # a graph repeats each source_file many times
    def key_of(source_file: str) -> str:
        return _cpp_source_key(source_file, root)

    batch = {_cpp_source_key(p, root) for p in paths}
    selected = (batch | {_cpp_source_key(p, root) for p in changed_paths}) - {""}
    owned = {key for key in selected if resolve_consumer_extractors(root / key)}
    if not owned:
        return paths
    hosted = {
        n.get("id")
        for n in graph.get("nodes", [])
        if key_of(n.get("source_file") or "") in owned
    }
    if not hosted:
        return paths
    allowed = {_cpp_source_key(p, root) for p in available_paths} - selected - {""}
    referrers: dict[str, set[str]] = {}
    for edge in graph.get("links", graph.get("edges", [])):
        ends = {edge.get("source"), edge.get("target")} & hosted
        source_file = edge.get("source_file")
        if not ends or not source_file:
            continue
        if key_of(source_file) in allowed:
            for nid in ends:
                referrers.setdefault(nid, set()).add(key_of(source_file))
    if not referrers:
        return paths
    # What the batch still emits stays; only the rest takes its edges with it.
    for key in sorted(batch & owned):
        path = root / key
        if not path.is_file():
            continue
        for extractor in resolve_consumer_extractors(path):
            try:
                emitted = extractor(path).get("nodes", [])
            except Exception:  # extract() reports the failure itself
                continue
            for node in emitted:
                referrers.pop(node.get("id"), None)
    lost = set().union(*referrers.values()) if referrers else set()
    return paths + [root / key for key in sorted(lost) if (root / key).is_file()]
