"""ODS BI ObjectScript extractor — delegates to ``shared.kg_extract`` SSOT."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _ensure_consumer_tools_on_path() -> None:
    """ODS / consumer repos import ``shared.*`` with ``tools/`` on ``sys.path`` (see pytest pythonpath)."""
    for parent in [Path.cwd(), *Path.cwd().parents]:
        tools = parent / "tools"
        marker = parent / "pyproject.toml"
        if tools.is_dir() and marker.is_file():
            entry = str(tools.resolve())
            if entry not in sys.path:
                sys.path.insert(0, entry)
            return


def extract_bi_cls(path: Path) -> dict[str, Any]:
    """
    Graphify entry point for ``src/BI/**/*.cls``.

    Fail fast: propagates :class:`ValueError` from ``shared.kg_extract`` (no empty fallback).
    """
    _ensure_consumer_tools_on_path()
    from shared.kg_extract.extract_bi_cls import extract_bi_cls_path

    return extract_bi_cls_path(path)


def extract_dfi(path: Path) -> dict[str, Any]:
    """
    Graphify entry point for ``src/BI/DFI/**/*.DFI``.

    Fail fast: propagates :class:`ValueError` from ``shared.kg_extract`` (no empty fallback).
    """
    _ensure_consumer_tools_on_path()
    from shared.kg_extract.extract_dfi import extract_dfi_path

    return extract_dfi_path(path)


def extract_objectscript_ast(path: Path) -> dict[str, Any]:
    """
    Graphify entry point for ObjectScript AST (``.cls``, ``.refcls`` reference mirrors, routines).

    Fail fast: propagates errors from ``shared.objectscript_ast`` (no Apex fallback).
    """
    _ensure_consumer_tools_on_path()
    from shared.objectscript_ast.extract import extract_objectscript_path

    return extract_objectscript_path(path)


def extract_csp(path: Path) -> dict[str, Any]:
    """
    Graphify entry point for ``reference/source_entities/**/*.refcsp``.

    Fail fast: propagates :class:`ValueError` from ``shared.kg_extract`` (no empty fallback).
    """
    _ensure_consumer_tools_on_path()
    from shared.kg_extract.extract_csp import extract_csp_path

    return extract_csp_path(path)
