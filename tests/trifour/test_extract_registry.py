"""Consumer extractor registration via ``[[tool.graphify.extractors]]``."""

from __future__ import annotations

from pathlib import Path

from graphify.detect import CODE_EXTENSIONS
from graphify.extract import (
    _DISPATCH,
    _bypass_ast_cache,
    _merge_extraction_results,
    _path_has_extractor,
    extract_objectscript,
)
from graphify.trifour.extract.registry import (
    resolve_consumer_extractor,
    resolve_consumer_extractors,
)


def _write_fake_consumer(root: Path) -> Path:
    """Install a tiny consumer extractor package under *root* for registry tests."""
    pkg = root / "consumer_ext"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "extract.py").write_text(
        """
from pathlib import Path

def extract_demo(path: Path) -> dict:
    return {"nodes": [{"id": path.stem, "label": path.name}], "edges": []}

def extract_other(path: Path) -> dict:
    return {"nodes": [{"id": path.stem + "_other", "label": "other"}], "edges": []}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return pkg


def test_consumer_extractor_routes_by_glob(tmp_path, monkeypatch):
    root = tmp_path
    _write_fake_consumer(root)
    src = root / "src" / "pkg"
    src.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "consumer_ext.extract"
function = "extract_demo"
extensions = [".cls"]
path_glob = "src/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cls = src / "Sample.cls"
    cls.write_text("Class Sample\n{\n}\n")
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root))

    fn = resolve_consumer_extractor(cls, project_root=root)
    assert fn is not None
    assert fn.__name__ == "extract_demo"

    other = root / "force-app" / "classes" / "Foo.cls"
    other.parent.mkdir(parents=True)
    other.write_text("public class Foo {}\n")
    assert resolve_consumer_extractor(other, project_root=root) is None


def test_consumer_extractor_bypasses_ast_cache(tmp_path, monkeypatch):
    root = tmp_path
    _write_fake_consumer(root)
    src = root / "src"
    src.mkdir()
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "consumer_ext.extract"
function = "extract_demo"
extensions = [".cls"]
path_glob = "src/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cls = src / "X.cls"
    cls.write_text("Class X\n{\n}\n")
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root))
    assert _bypass_ast_cache(cls) is True
    other = root / "Other.cls"
    other.write_text("class Other\n")
    assert _bypass_ast_cache(other) is False


def test_dfi_and_refcsp_in_code_extensions() -> None:
    assert ".dfi" in CODE_EXTENSIONS
    assert ".refcsp" in CODE_EXTENSIONS


def test_consumer_owned_paths_skip_no_ast_extractor_warning(tmp_path, monkeypatch):
    """#1689 must not fire when ``[[tool.graphify.extractors]]`` owns the path."""
    root = tmp_path
    _write_fake_consumer(root)
    ref = root / "reference" / "source_entities"
    ref.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "consumer_ext.extract"
function = "extract_demo"
extensions = [".refcsp"]
path_glob = "reference/source_entities/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    csp = ref / "Demo.refcsp"
    csp.write_text("<html></html>\n")
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root))
    assert _path_has_extractor(csp) is True


def test_consumer_only_path_uses_consumer_extractor_in_worker(tmp_path, monkeypatch):
    """Consumer-only extensions must not short-circuit on missing built-in dispatch."""
    root = tmp_path
    _write_fake_consumer(root)
    src = root / "reference" / "source_entities"
    src.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "consumer_ext.extract"
function = "extract_demo"
extensions = [".refcsp"]
path_glob = "reference/source_entities/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    csp = src / "Demo.refcsp"
    csp.write_text("<html></html>\n")
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root))

    from graphify.extract import _extract_single_file

    idx, result = _extract_single_file(
        (0, str(csp.resolve()), str(root.resolve()), str(root.resolve()))
    )
    assert idx == 0
    assert result.get("nodes")
    assert result["nodes"][0]["id"] == "Demo"


def test_multiple_consumer_extractors(tmp_path, monkeypatch):
    root = tmp_path
    _write_fake_consumer(root)
    src = root / "src"
    src.mkdir()
    (root / "pyproject.toml").write_text(
        """
[tool.graphify]
[[tool.graphify.extractors]]
module = "consumer_ext.extract"
function = "extract_demo"
extensions = [".cls"]
path_glob = "src/**"
[[tool.graphify.extractors]]
module = "consumer_ext.extract"
function = "extract_other"
extensions = [".cls"]
path_glob = "src/**"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cls = src / "Sample.cls"
    cls.write_text("Class Sample\n{\n}\n")
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root))
    names = [fn.__name__ for fn in resolve_consumer_extractors(cls, project_root=root)]
    assert names == ["extract_demo", "extract_other"]


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
    assert _DISPATCH[".cls"] is extract_objectscript
    assert _DISPATCH[".refcls"] is extract_objectscript


def test_objectscript_extensions_in_code_extensions() -> None:
    for ext in (".mac", ".int", ".os", ".rtn", ".refcls"):
        assert ext in CODE_EXTENSIONS


def test_post_extract_merge_config_no_op_without_spec(tmp_path):
    from graphify.trifour.extract.post import merge_consumer_kg_extensions

    result = {"nodes": [{"id": "a"}], "edges": []}
    out = merge_consumer_kg_extensions(
        result, project_root=tmp_path, full_rebuild=True
    )
    assert out is result
