"""Stable contracts for interactive graph visualization (merge-safe, no product imports)."""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class GraphDocument(TypedDict):
    """Node-link graph document for serve transforms."""

    meta: dict[str, Any]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class GraphLoader(Protocol):
    def load(
        self, graph_path: str, *, out_dir: str | None = None
    ) -> GraphDocument: ...


class ViewTransform(Protocol):
    def apply(
        self,
        doc: GraphDocument,
        *,
        view_mode: str,
        focus_community_ids: list[int],
        expansion_mode: str,
        neighborhood_hop: int,
        max_nodes: int,
    ) -> GraphDocument: ...


class GroupingStrategy(Protocol):
    def group_ids(
        self, doc: GraphDocument, *, dimension: str, **params: Any
    ) -> dict[str, int]: ...

    def label_group(
        self,
        doc: GraphDocument,
        group_id: str,
        member_ids: list[str],
        *,
        labels: dict[int, str] | None = None,
    ) -> str: ...
