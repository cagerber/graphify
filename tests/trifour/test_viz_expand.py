"""Tests for trifour viz expansion."""

from __future__ import annotations

import pytest

from graphify.trifour.viz.expand import ExpansionBudgetError, apply_expansion
from graphify.trifour.viz.load import load_document
from graphify.viz_contract import GraphDocument


def _sample_doc() -> GraphDocument:
    return GraphDocument(
        meta={"documentType": "graphify"},
        nodes=[
            {"id": "a", "community": 0, "label": "A"},
            {"id": "b", "community": 0, "label": "B"},
            {"id": "c", "community": 1, "label": "C"},
            {"id": "d", "community": 2, "label": "D"},
        ],
        edges=[
            {"source": "a", "target": "b", "relation": "calls"},
            {"source": "b", "target": "c", "relation": "calls"},
            {"source": "c", "target": "d", "relation": "imports"},
        ],
    )


@pytest.mark.unit
def test_neighborhood_expand_includes_adjacent_community() -> None:
    doc = _sample_doc()
    out = apply_expansion(
        doc,
        view_mode="expanded_communities",
        focus_community_ids=[0],
        expansion_mode="neighborhood",
        neighborhood_hop=1,
        max_nodes=100,
    )
    ids = {n["id"] for n in out["nodes"]}
    assert "a" in ids and "b" in ids
    assert "c" in ids


@pytest.mark.unit
def test_expansion_budget_raises() -> None:
    doc = _sample_doc()
    with pytest.raises(ExpansionBudgetError):
        apply_expansion(
            doc,
            view_mode="expanded_communities",
            focus_community_ids=[0, 1, 2],
            expansion_mode="neighborhood",
            neighborhood_hop=2,
            max_nodes=2,
        )


@pytest.mark.unit
def test_aggregated_view_meta_nodes(tmp_path) -> None:
    graph = {
        "nodes": [
            {"id": "n1", "community": 0, "label": "one"},
            {"id": "n2", "community": 1, "label": "two"},
        ],
        "links": [{"source": "n1", "target": "n2", "relation": "calls"}],
    }
    path = tmp_path / "graph.json"
    path.write_text(__import__("json").dumps(graph), encoding="utf-8")
    doc = load_document(path)
    out = apply_expansion(doc, view_mode="aggregated_communities", max_nodes=100)
    assert len(out["nodes"]) == 2
    assert out["meta"].get("aggregated") is True
