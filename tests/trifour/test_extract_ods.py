"""Consumer extractor registration for ODS BI ``.cls`` files."""

from __future__ import annotations

from pathlib import Path

from graphify.extract import _bypass_ast_cache, _get_extractors, _merge_extraction_results
from graphify.trifour.extract.registry import (
    resolve_consumer_extractor,
    resolve_consumer_extractors,
)


def test_bi_cls_uses_ods_extractor_not_apex(tmp_path, monkeypatch):
    """``src/BI/**/*.cls`` must route to graphify.trifour.extract.ods, not Apex."""
    root = tmp_path
    bi = root / "src" / "BI" / "Dimensions"
    bi.mkdir(parents=True)
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "graphify.trifour.extract.ods"
function = "extract_bi_cls"
extensions = [".cls"]
path_glob = "src/BI/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cls = bi / "Sample.cls"
    cls.write_text("Class BI.Dimensions.Sample Extends %RegisteredObject\n{\n}\n")

    monkeypatch.chdir(root)

    fn = resolve_consumer_extractor(cls, project_root=root)
    assert fn is not None
    assert fn.__module__ == "graphify.trifour.extract.ods"
    assert fn.__name__ == "extract_bi_cls"

    other = root / "force-app" / "classes" / "Foo.cls"
    other.parent.mkdir(parents=True)
    other.write_text("public class Foo {}\n")
    apex_fn = resolve_consumer_extractor(other, project_root=root)
    assert apex_fn is None


def test_consumer_extractor_bypasses_ast_cache(tmp_path, monkeypatch):
    root = tmp_path
    bi = root / "src" / "BI" / "Cubes"
    bi.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "graphify.trifour.extract.ods"
function = "extract_bi_cls"
extensions = [".cls"]
path_glob = "src/BI/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cls = bi / "X.cls"
    cls.write_text("Class BI.Cubes.X\n{\n}\n")
    monkeypatch.chdir(root)
    assert _bypass_ast_cache(cls) is True
    other = root / "Other.cls"
    other.write_text("class Other\n")
    assert _bypass_ast_cache(other) is False


def test_dfi_uses_ods_extractor(tmp_path, monkeypatch):
    root = tmp_path
    dfi = root / "src" / "BI" / "DFI"
    dfi.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "graphify.trifour.extract.ods"
function = "extract_dfi"
extensions = [".DFI"]
path_glob = "src/BI/DFI/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    pivot = dfi / "X.pivot.DFI"
    pivot.write_text('<?xml version="1.0"?><pivot name="X" folderName="F" cubeName="C"/>')
    monkeypatch.chdir(root)
    fn = resolve_consumer_extractor(pivot, project_root=root)
    assert fn is not None
    assert fn.__name__ == "extract_dfi"


def test_dfi_in_code_extensions() -> None:
    from graphify.detect import CODE_EXTENSIONS

    assert ".dfi" in CODE_EXTENSIONS


def test_refcsp_in_code_extensions() -> None:
    from graphify.detect import CODE_EXTENSIONS

    assert ".refcsp" in CODE_EXTENSIONS


def test_refcsp_uses_ods_extractor(tmp_path, monkeypatch):
    root = tmp_path
    ref = root / "reference" / "source_entities" / "Reports"
    ref.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "graphify.trifour.extract.ods"
function = "extract_csp"
extensions = [".refcsp"]
path_glob = "reference/source_entities/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    csp = ref / "RptFoo.refcsp"
    csp.write_text(
        '<script language="sql" name="q">SELECT ID FROM DataEntities.Hospital</script>\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(root)
    fn = resolve_consumer_extractor(csp, project_root=root)
    assert fn is not None
    assert fn.__name__ == "extract_csp"


def test_bi_cls_resolves_multiple_consumer_extractors(tmp_path, monkeypatch):
    """``src/BI/**/*.cls`` may register both AST and BI extractors."""
    root = tmp_path
    bi = root / "src" / "BI" / "Dimensions"
    bi.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "graphify.trifour.extract.ods"
function = "extract_objectscript_ast"
extensions = [".cls"]
path_glob = "src/**"
[[tool.graphify.extractors]]
module = "graphify.trifour.extract.ods"
function = "extract_bi_cls"
extensions = [".cls"]
path_glob = "src/BI/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cls = bi / "Sample.cls"
    cls.write_text("Class BI.Dimensions.Sample Extends %RegisteredObject\n{\n}\n")
    monkeypatch.chdir(root)
    fns = resolve_consumer_extractors(cls, project_root=root)
    names = [fn.__name__ for fn in fns]
    assert names == ["extract_objectscript_ast", "extract_bi_cls"]


def test_merge_extraction_results_concatenates_nodes() -> None:
    merged = _merge_extraction_results(
        [
            {"nodes": [{"id": "a"}], "edges": []},
            {"nodes": [{"id": "b"}], "edges": [{"source": "a", "target": "b"}]},
        ]
    )
    assert len(merged["nodes"]) == 2
    assert len(merged["edges"]) == 1


def test_cls_builtin_dispatch_is_objectscript_not_apex() -> None:
    from graphify.extract import _DISPATCH, extract_objectscript

    assert _DISPATCH[".cls"] is extract_objectscript
    assert _DISPATCH[".refcls"] is extract_objectscript


def test_objectscript_extensions_in_code_extensions() -> None:
    from graphify.detect import CODE_EXTENSIONS

    for ext in (".mac", ".int", ".os", ".rtn", ".refcls"):
        assert ext in CODE_EXTENSIONS
