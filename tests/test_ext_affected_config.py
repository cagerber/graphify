"""Consumer relation names in `affected`, and loud consumer-extractor import failure."""
from __future__ import annotations

import networkx as nx
import pytest

from graphify.affected import format_affected, resolve_seed
from graphify.extract import _get_extractors, extract


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


def test_cross_file_reference_stub_reaches_the_definition(tmp_path, monkeypatch):
    root = _project(
        tmp_path,
        monkeypatch,
        '[[tool.graphify.extractors]]\nmodule = "zz_stub_extractor"\n'
        'function = "extract_zz"\nextensions = [".zz"]\n',
    )
    (root / "zz_stub_extractor.py").write_text(
        "def extract_zz(path):\n"
        "    rel = path.name\n"
        "    own = {'id': 'sym_' + path.stem, 'label': path.stem, 'node_ref': 'P.' + path.stem,\n"
        "           'file_type': 'code', 'source_file': rel}\n"
        "    if path.stem == 'b':\n"
        "        return {'nodes': [own], 'edges': []}\n"
        "    stub = {'id': 'sym_b', 'label': 'b', 'file_type': 'code', 'source_file': rel, 'ref_stub': True}\n"
        "    edge = {'source': 'sym_a', 'target': 'sym_b', 'relation': 'calls', 'source_file': rel,\n"
        "            'confidence': 'EXTRACTED'}\n"
        "    return {'nodes': [own, stub], 'edges': [edge]}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))
    for name in ("a.zz", "b.zz"):
        (root / name).write_text("x", encoding="utf-8")

    result = extract([root / "a.zz", root / "b.zz"], root=root, cache_root=root, parallel=False)

    ids = [n["id"] for n in result["nodes"]]
    assert ids.count("sym_b") == 1
    assert [(e["source"], e["target"]) for e in result["edges"] if e["relation"] == "calls"] == [
        ("sym_a", "sym_b")
    ]
    graph = nx.DiGraph()
    for node in result["nodes"]:
        graph.add_node(node["id"], **node)
    assert resolve_seed(graph, "P.b") == "sym_b"
