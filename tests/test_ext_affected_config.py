"""Consumer relation names in `affected`, and loud consumer-extractor import failure."""
from __future__ import annotations

import networkx as nx
import pytest

from graphify.affected import format_affected
from graphify.extract import _get_extractors


def _project(tmp_path, monkeypatch, body):
    monkeypatch.delenv("GRAPHIFY_CONFIG", raising=False)
    (tmp_path / "pyproject.toml").write_text(body, encoding="utf-8")
    return tmp_path


def test_affected_follows_configured_relations_both_directions(tmp_path, monkeypatch):
    root = _project(
        tmp_path,
        monkeypatch,
        '[tool.graphify]\naffected_relations = ["x.calls"]\n'
        'affected_relations_reversed = ["x.feeds"]\n',
    )
    graph = nx.DiGraph()
    for name in ("dep", "caller", "consumer", "other"):
        graph.add_node(name, label=name)
    graph.add_edge("caller", "dep", relation="x.calls")
    graph.add_edge("dep", "consumer", relation="x.feeds")
    graph.add_edge("dep", "other", relation="x.calls")

    out = format_affected(graph, "dep", root=root, seed="dep")

    assert "- caller [x.calls]" in out
    assert "- consumer [x.feeds]" in out
    assert "- other" not in out


def test_unimportable_consumer_extractor_raises(tmp_path, monkeypatch):
    root = _project(
        tmp_path,
        monkeypatch,
        '[[tool.graphify.extractors]]\nmodule = "no_such_module_here"\n'
        'function = "extract"\nextensions = [".zz"]\n',
    )
    source = root / "a.zz"
    source.write_text("x", encoding="utf-8")

    with pytest.raises(ImportError, match="no_such_module_here"):
        _get_extractors(source)
