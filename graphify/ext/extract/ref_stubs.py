"""Fold consumer reference stubs into the node that defines the symbol.

A consumer extractor sees one file at a time, so a call into another file needs a
placeholder node carrying the callee's id. It marks that node ``ref_stub``. Left
in place, the placeholder and the definition are one id from two files, which the
id disambiguation splits apart, so no cross-file edge reaches the definition.
"""
from __future__ import annotations

from typing import Iterable

__all__ = ["fold_ref_stubs"]


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
