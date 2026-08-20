"""Node kind metadata for AST extraction (file, class, function, …)."""

from __future__ import annotations

from pathlib import Path

from graphify.node_paths import normalize_source_path

KIND_FILE = "file"
KIND_CLASS = "class"
KIND_FUNCTION = "function"
KIND_METHOD = "method"
KIND_IMPORT = "import"
KIND_OTHER = "other"

ALL_KINDS = frozenset(
    {KIND_FILE, KIND_CLASS, KIND_FUNCTION, KIND_METHOD, KIND_IMPORT, KIND_OTHER}
)


def is_file_hub_label(source_file: str, label: str) -> bool:
    if not source_file or not label:
        return False
    return Path(normalize_source_path(source_file)).name == label


def infer_kind_from_label(label: str, *, parent_is_class: bool = False) -> str:
    text = (label or "").strip()
    if text.startswith(".") and text.endswith("()"):
        return KIND_METHOD
    if text.endswith("()"):
        return KIND_METHOD if parent_is_class else KIND_FUNCTION
    return KIND_OTHER


def finalize_node_kinds(nodes: list[dict]) -> None:
    """Ensure every node has ``kind``; infer from label shape when unset.

    Order matters: file hubs (label == source basename) win, then methods
    (``.name()``), functions (``name()``), classes (PascalCase identifier),
    everything else is ``other``.
    """
    for node in nodes:
        if node.get("kind") in ALL_KINDS:
            continue
        source_file = node.get("source_file") or ""
        label = node.get("label") or ""
        if is_file_hub_label(source_file, label):
            node["kind"] = KIND_FILE
        elif label.startswith(".") and label.endswith("()"):
            node["kind"] = KIND_METHOD
        elif label.endswith("()"):
            node["kind"] = KIND_FUNCTION
        elif label[:1].isupper() and label.replace("_", "").isalnum():
            node["kind"] = KIND_CLASS
        else:
            node["kind"] = KIND_OTHER
