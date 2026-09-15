"""Load ``[tool.graphify]`` from consumer ``pyproject.toml`` (no hardcoded repo paths)."""

from __future__ import annotations

import fnmatch
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TestsCoversRule:
    """Map test file globs to production paths via explicit strip rules."""

    test: str
    strip_prefix: str = "tests/"
    strip_test_filename_prefix: str = "test_"
    collapse_tests_dir: bool = False


@dataclass
class ExtractorRule:
    """Consumer-registered file extractor (``[[tool.graphify.extractors]]``)."""

    module: str
    function: str
    extensions: tuple[str, ...]
    path_glob: str = ""


@dataclass
class GraphifyConfig:
    test_roots: list[str] = field(default_factory=lambda: ["tests"])
    tests_covers: list[TestsCoversRule] = field(default_factory=list)
    folder_prefix_depth: int = 2
    folder_edges: bool = True
    folder_affinity: bool = True
    pytest_enrich: bool = True
    heuristic_labels: bool = False
    extractors: list[ExtractorRule] = field(default_factory=list)
    # Suffixes the consumer declares as source code. Extensions named by an
    # ``[[tool.graphify.extractors]]`` rule are always included, so a rule is the
    # single place to declare a consumer-owned language.
    code_extensions: list[str] = field(default_factory=list)
    # Optional ``module:function`` invoked after full AST rebuild (consumer KG extensions).
    post_extract_merge: str = ""


def _env_bool(name: str, default: bool) -> bool:
    """Resolve a boolean from env when set; otherwise use *default*."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() not in ("0", "false", "no", "off")


def enrich_flags(project_root: Path | str | None = None) -> dict[str, bool]:
    """Merge ``[tool.graphify]`` enrich defaults with ``GRAPHIFY_*`` env overrides."""
    cfg = load_graphify_config(project_root)
    return {
        "folder_edges": _env_bool("GRAPHIFY_FOLDER_EDGES", cfg.folder_edges),
        "folder_affinity": _env_bool("GRAPHIFY_FOLDER_AFFINITY", cfg.folder_affinity),
        "pytest_enrich": _env_bool("GRAPHIFY_PYTEST_ENRICH", cfg.pytest_enrich),
        "heuristic_labels": _env_bool("GRAPHIFY_HEURISTIC_LABELS", cfg.heuristic_labels),
    }


_CONFIG_CACHE: dict[tuple[str, int, int], "GraphifyConfig"] = {}


def _find_pyproject(root: Path) -> Path | None:
    for parent in [root, *root.parents]:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def load_graphify_config(root: Path | str | None = None) -> GraphifyConfig:
    """Load ``[tool.graphify]`` from the nearest ``pyproject.toml`` upward from *root*.

    Cached per file signature: extractor dispatch resolves the config once per
    file, and re-parsing the TOML every time cost ~0.4 ms/file. A rewrite changes
    ``mtime_ns``/size, so the entry is replaced rather than reused.
    """
    base = Path(root or ".").resolve()
    pyproject = _find_pyproject(base)
    if pyproject is None:
        return GraphifyConfig()

    try:
        stat = pyproject.stat()
    except OSError:
        return GraphifyConfig()
    key = (str(pyproject), stat.st_mtime_ns, stat.st_size)
    cached = _CONFIG_CACHE.get(key)
    if cached is not None:
        return cached

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return GraphifyConfig()

    section: dict[str, Any] = data.get("tool", {}).get("graphify", {})
    if not section:
        _remember_config(key, GraphifyConfig())
        return GraphifyConfig()

    rules: list[TestsCoversRule] = []
    for item in section.get("tests_covers", []):
        if not isinstance(item, dict):
            continue
        test_pat = item.get("test")
        if not test_pat:
            continue
        rules.append(
            TestsCoversRule(
                test=str(test_pat),
                strip_prefix=str(item.get("strip_prefix", "tests/")),
                strip_test_filename_prefix=str(
                    item.get("strip_test_filename_prefix", "test_")
                ),
                collapse_tests_dir=bool(item.get("collapse_tests_dir", False)),
            )
        )

    test_roots = section.get("test_roots", ["tests"])
    if isinstance(test_roots, str):
        test_roots = [test_roots]

    depth = section.get("folder_prefix_depth", 2)
    try:
        folder_prefix_depth = int(depth)
    except (TypeError, ValueError):
        folder_prefix_depth = 2

    extractors: list[ExtractorRule] = []
    for item in section.get("extractors", []):
        if not isinstance(item, dict):
            continue
        module = str(item.get("module") or "").strip()
        function = str(item.get("function") or "").strip()
        if not module or not function:
            continue
        raw_ext = item.get("extensions", [])
        if isinstance(raw_ext, str):
            extensions = (raw_ext,)
        else:
            extensions = tuple(str(x).strip().lower() for x in raw_ext if str(x).strip())
        if not extensions:
            continue
        path_glob = str(item.get("path_glob") or "").strip()
        extractors.append(
            ExtractorRule(
                module=module,
                function=function,
                extensions=extensions,
                path_glob=path_glob,
            )
        )

    raw_code_ext = section.get("code_extensions", [])
    if isinstance(raw_code_ext, str):
        raw_code_ext = [raw_code_ext]
    code_extensions = [
        str(x).strip().lower() for x in raw_code_ext if str(x).strip()
    ]

    cfg = GraphifyConfig(
        test_roots=[str(r) for r in test_roots],
        tests_covers=rules,
        folder_prefix_depth=folder_prefix_depth,
        folder_edges=bool(section.get("folder_edges", True)),
        folder_affinity=bool(section.get("folder_affinity", True)),
        pytest_enrich=bool(section.get("pytest_enrich", True)),
        heuristic_labels=bool(section.get("heuristic_labels", False)),
        extractors=extractors,
        code_extensions=code_extensions,
        post_extract_merge=str(section.get("post_extract_merge") or "").strip(),
    )
    _remember_config(key, cfg)
    return cfg


def _remember_config(key: tuple[str, int, int], cfg: GraphifyConfig) -> None:
    """Cache a parsed config; drop the rest once the cache grows (tests use many tmp repos)."""
    if len(_CONFIG_CACHE) > 64:
        _CONFIG_CACHE.clear()
    _CONFIG_CACHE[key] = cfg


def consumer_code_extensions(root: Path | str | None = None) -> frozenset[str]:
    """Suffixes the consumer's own configuration declares as source code.

    A consumer-owned language is declared once — in the
    ``[[tool.graphify.extractors]]`` rule that extracts it — so code detection
    (``graphify.detect.CODE_EXTENSIONS``), the watch trigger and the "no
    extractor" diagnostics all agree with the extraction rules by construction.
    ``[tool.graphify] code_extensions`` adds suffixes that have no rule (a
    format that is code but is not extracted), and ``GRAPHIFY_CODE_EXTENSIONS``
    (comma or space separated) overrides for runs whose working directory is
    outside the consumer project.
    """
    cfg = load_graphify_config(root)
    suffixes = {_normalize_suffix(ext) for ext in cfg.code_extensions}
    for rule in cfg.extractors:
        suffixes.update(_normalize_suffix(ext) for ext in rule.extensions)
    raw_env = os.environ.get("GRAPHIFY_CODE_EXTENSIONS", "")
    for item in re.split(r"[,\s]+", raw_env):
        if item.strip():
            suffixes.add(_normalize_suffix(item))
    suffixes.discard("")
    return frozenset(suffixes)


def _normalize_suffix(ext: str) -> str:
    value = str(ext).strip().lower()
    if not value:
        return ""
    return value if value.startswith(".") else f".{value}"


def match_glob(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return fnmatch.fnmatch(normalized, pattern)


def production_path_for_test(test_path: str, rule: TestsCoversRule) -> str | None:
    """Return production path when *test_path* matches *rule.test*; else None."""
    normalized = test_path.replace("\\", "/").lstrip("./")
    if not match_glob(normalized, rule.test):
        return None
    rel = normalized
    if rule.collapse_tests_dir:
        rel = rel.replace("/tests/", "/", 1)
    if rule.strip_prefix and rel.startswith(rule.strip_prefix):
        rel = rel[len(rule.strip_prefix) :].lstrip("/")
    path = Path(rel)
    name = path.name
    if name.startswith("test_") and name.endswith(".py"):
        name = name[5:]
    elif rule.strip_test_filename_prefix and name.startswith(rule.strip_test_filename_prefix):
        name = name[len(rule.strip_test_filename_prefix) :]
    if path.parent != Path("."):
        return str(path.parent / name).replace("\\", "/")
    return name
