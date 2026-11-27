"""Consumer relation names in `affected`, and loud consumer-extractor import failure."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

import graphify
from graphify.affected import affected_nodes, format_affected, resolve_seed
from graphify.ext.query.callers import direct_callers_text
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


def test_path_and_explain_resolve_a_node_ref():
    import networkx as nx

    from graphify.serve import _find_node, _resolve_path_endpoint

    graph = nx.DiGraph()
    graph.add_node("m", label="Record", node_ref="App.Utils.Status.Record", file_type="code")
    graph.add_node("other", label="Record", node_ref="App.Other.Record", file_type="code")
    graph.add_node("stub", label="Record", node_ref="App.Utils.Status.Record", file_type="concept")

    assert _find_node(graph, "App.Utils.Status.Record") == ["m"]
    assert _resolve_path_endpoint(graph, "App.Utils.Status.Record()")[0] == "m"


def test_namespaced_calls_members_and_derived_locations():
    import networkx as nx

    from graphify.affected import format_affected
    from graphify.ext.query.callers import direct_callers_text

    graph = nx.DiGraph()
    graph.add_node("cls", label="Status", source_file="Status.cls", source_location="L1")
    graph.add_node("m", label="Record", source_file="Status.cls", source_location="L5")
    graph.add_node("c", label="Run", source_file="Run.cls", source_location="L2")
    graph.add_edge("m", "cls", relation="structural.member_of")
    graph.add_edge(
        "c", "m", relation="structural.calls",
        source_file="x/.graphify-derived", source_location="L1",
    )

    assert "<-- Run [structural.calls]" in direct_callers_text(graph, "Record")
    text = format_affected(graph, "Status", relations=("structural.calls",), seed="cls")
    assert "- Run [structural.calls] Run.cls:L2" in text


_ZZ_EXTRACTOR = """
def extract_zz(path):
    own = "sym:file:" + path.stem
    nodes = [{"id": own, "label": path.stem, "file_type": "code", "source_file": str(path)}]
    edges = []
    for line in path.read_text().splitlines():
        kind, _, name = line.partition(" ")
        node = {"id": "sym:" + name, "label": name, "node_ref": "P." + name,
                "file_type": "concept", "source_file": str(path)}
        if kind == "def":
            nodes.append(node)
        else:
            nodes.append({**node, "ref_stub": True})
            edges.append({"source": own, "target": "sym:" + name, "relation": "ns.calls",
                          "source_file": str(path), "confidence": "EXTRACTED"})
    return {"nodes": nodes, "edges": edges}
"""


def _zz_corpus(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    (tmp_path / "zz_ext.py").write_text(_ZZ_EXTRACTOR, encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[tool.graphify]\naffected_relations = ["ns.calls"]\n'
        '[[tool.graphify.extractors]]\nmodule = "zz_ext"\n'
        'function = "extract_zz"\nextensions = [".zz"]\n',
        encoding="utf-8",
    )
    return root


def _cli(root, *args, **env):
    environ = {
        k: v for k, v in os.environ.items() if k not in ("GRAPHIFY_OUT", "GRAPHIFY_CONFIG")
    }
    # The graphify under test, then the directory holding the corpus extractor.
    search = [str(Path(graphify.__file__).parents[1]), str(root.parent)]
    environ.update(GRAPHIFY_BACKEND="none", PYTHONPATH=os.pathsep.join(search), **env)
    done = subprocess.run(
        [sys.executable, "-m", "graphify", *args],
        cwd=root, env=environ, capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "minted by two different files" not in done.stderr, done.stderr
    return done.stdout


def _calls_and_symbol(root):
    """(callers of sym:X, the nodes standing for X) in the built graph."""
    data = json.loads((root / "graphify-out" / "graph.json").read_text(encoding="utf-8"))
    edges = data.get("links", data.get("edges"))
    callers = sorted(e["source"] for e in edges if e["relation"] == "ns.calls")
    targets = {e["target"] for e in edges if e["relation"] == "ns.calls"}
    nodes = [n for n in data["nodes"] if n.get("node_ref") == "P.X"]
    assert targets <= {"sym:X"}
    return callers, [(n["id"], n["source_file"], bool(n.get("ref_stub"))) for n in nodes]


_BUILDS = {"update": ("update", "."), "extract": ("extract", ".", "--code-only")}
_BOTH = ["sym:file:a", "sym:file:b"]


@pytest.mark.parametrize("command", sorted(_BUILDS))
def test_incremental_new_definition_and_caller_join_a_saved_stub(tmp_path, command):
    root = _zz_corpus(tmp_path)
    (root / "a.zz").write_text("call X\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])
    (root / "d.zz").write_text("def X\n", encoding="utf-8")
    (root / "b.zz").write_text("call X\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])

    assert _calls_and_symbol(root) == (_BOTH, [("sym:X", "d.zz", False)])


@pytest.mark.parametrize("change", ["call removed", "file deleted"])
@pytest.mark.parametrize("command", sorted(_BUILDS))
def test_incremental_keeps_other_callers_when_the_stub_host_changes(tmp_path, command, change):
    root = _zz_corpus(tmp_path)
    # The host (first file) also loses nodes. The other file repeats a definition,
    # so extracting it again would count a dedup merge and the write be refused.
    (root / "a.zz").write_text("call X\ndef P\ndef Q\n", encoding="utf-8")
    (root / "b.zz").write_text("call X\ndef D\ndef D\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])
    host = _calls_and_symbol(root)[1][0][1]
    assert host == "a.zz"
    other = "b"
    if change == "file deleted":
        (root / host).unlink()
    else:
        (root / host).write_text("def R\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])

    assert _calls_and_symbol(root) == (
        ["sym:file:" + other], [("sym:X", other + ".zz", True)]
    )


@pytest.mark.parametrize("command", sorted(_BUILDS))
def test_incremental_new_reference_to_a_saved_stub_while_nodes_go(tmp_path, command):
    root = _zz_corpus(tmp_path)
    (root / "a.zz").write_text("call X\n", encoding="utf-8")
    (root / "b.zz").write_text("def P\ndef Q\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])
    (root / "b.zz").write_text("call X\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])

    callers, nodes = _calls_and_symbol(root)
    assert callers == _BOTH and [n[0] for n in nodes] == ["sym:X"]


def test_incremental_no_cluster_keeps_other_callers_when_the_stub_host_goes(tmp_path):
    root = _zz_corpus(tmp_path)
    build = ("extract", ".", "--code-only", "--no-cluster")
    for name in ("a.zz", "b.zz"):
        (root / name).write_text("call X\n", encoding="utf-8")
    _cli(root, *build)
    host = _calls_and_symbol(root)[1][0][1]
    other = "b" if host == "a.zz" else "a"
    (root / host).unlink()
    _cli(root, *build)

    assert _calls_and_symbol(root) == (
        ["sym:file:" + other], [("sym:X", other + ".zz", True)]
    )


@pytest.mark.parametrize("command", sorted(_BUILDS))
def test_incremental_definition_removed_and_restored(tmp_path, command):
    root = _zz_corpus(tmp_path)
    (root / "d.zz").write_text("def X\n", encoding="utf-8")
    for name in ("a.zz", "b.zz"):
        (root / name).write_text("call X\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])

    (root / "d.zz").write_text("def Y\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])
    callers, nodes = _calls_and_symbol(root)
    assert callers == _BOTH and [n[2] for n in nodes] == [True]

    (root / "d.zz").write_text("def Y\ndef X\n", encoding="utf-8")
    _cli(root, *_BUILDS[command])
    assert _calls_and_symbol(root) == (_BOTH, [("sym:X", "d.zz", False)])


def test_cli_affected_reads_config_of_a_project_with_external_output(tmp_path):
    root = _zz_corpus(tmp_path)
    (root / "d.zz").write_text("def X\n", encoding="utf-8")
    (root / "a.zz").write_text("call X\n", encoding="utf-8")
    out = str(tmp_path / "elsewhere")
    _cli(root, "update", ".", GRAPHIFY_OUT=out)

    shown = _cli(root, "affected", "P.X", GRAPHIFY_OUT=out)

    assert "- a [ns.calls]" in shown


def _class_graph():
    """One class seen three ways, plus a data-file node labelled with its name."""
    graph = nx.DiGraph()
    ref = "App.Data.Thing"
    graph.add_node("data", label="app.data.thing", file_type="code", source_file="counts.yaml")
    graph.add_node("inv", label="Thing", node_ref=ref, file_type="concept", source_file="inv.txt")
    graph.add_node("map", label=ref, node_ref=ref, file_type="concept", source_file="map.txt")
    graph.add_node("cls", label="Thing", node_ref=ref, file_type="concept", source_file="Thing.src")
    graph.add_node("prop", label="Name", node_ref=ref + ".Name", source_file="Thing.src")
    graph.add_node("view", label="Name", node_ref=ref + ".Name", source_file="map.txt")
    graph.add_node("report", label="report", source_file="r.txt")
    graph.add_node("cube", label="cube", source_file="c.txt")
    graph.add_node("caller", label="caller", source_file="x.txt")
    graph.add_edge("prop", "cls", relation="x.member_of")
    graph.add_edge("cls", "inv", relation="x.same_as")
    graph.add_edge("cls", "map", relation="x.same_as")
    graph.add_edge("report", "inv", relation="references")
    graph.add_edge("cube", "map", relation="references")
    graph.add_edge("caller", "cls", relation="x.calls")
    return graph


@pytest.mark.parametrize("memberless", [False, True])
def test_class_name_resolves_to_the_declaring_node(memberless):
    from graphify.serve import _resolve_path_endpoint, _resolve_single_node

    graph = _class_graph()
    if memberless:
        graph.remove_node("prop")

    assert resolve_seed(graph, "App.Data.Thing") == "cls"
    assert _resolve_single_node(graph, "App.Data.Thing")[0] == "cls"
    assert _resolve_path_endpoint(graph, "App.Data.Thing")[0] == "cls"
    assert direct_callers_text(graph, "App.Data.Thing").startswith("Direct callers of Thing (id=cls;")


@pytest.mark.parametrize("seed", ["cls", "inv"])
def test_affected_counts_users_of_every_view_of_a_class(seed):
    hits = {h.node_id for h in affected_nodes(_class_graph(), seed, relations=("references", "x.calls"))}

    assert hits == {"report", "cube", "caller"}


def test_affected_follows_the_views_of_a_class_reached_on_the_way():
    graph = _class_graph()
    graph.add_node("table", label="table")
    graph.add_edge("inv", "table", relation="references")

    hits = {h.node_id for h in affected_nodes(graph, "table", relations=("references",), depth=3)}

    assert {"inv", "report", "cube"} <= hits


def test_a_name_declared_twice_stays_ambiguous_despite_a_matching_label():
    graph = _class_graph()
    graph.add_node("cls2", label="Thing", node_ref="App.Data.Thing", source_file="copy.src")
    graph.add_node("prop2", label="Name", node_ref="App.Data.Thing.Other", source_file="copy.src")
    graph.add_edge("prop2", "cls2", relation="x.member_of")

    assert resolve_seed(graph, "App.Data.Thing") is None
