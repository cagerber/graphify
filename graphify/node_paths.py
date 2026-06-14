"""Path helpers for structural enrich and heuristic labels."""

from __future__ import annotations

from pathlib import Path

from graphify.paths import skip_dir_names

SKIP_DIR_PARTS = skip_dir_names()

CODE_EXTENSIONS = (
    ".py",
    ".cls",
    ".md",
    ".mac",
    ".js",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
)


def normalize_source_path(source_file: str) -> str:
    return source_file.replace("\\", "/").lstrip("./")


def source_path_parts(source_file: str) -> tuple[str, ...]:
    normalized = normalize_source_path(source_file)
    if not normalized:
        return ()
    return tuple(
        part
        for part in Path(normalized).parts
        if part not in SKIP_DIR_PARTS and not part.startswith(".")
    )


def parent_directory(source_file: str) -> str | None:
    parts = source_path_parts(source_file)
    if not parts:
        return None
    if len(parts) == 1:
        return ""
    return "/".join(parts[:-1])


def path_prefix(source_file: str, depth: int = 2) -> str | None:
    parts = list(source_path_parts(source_file))
    if not parts:
        return None
    if len(parts) > 1 and parts[-1].lower().endswith(CODE_EXTENSIONS):
        parts = parts[:-1]
    if not parts:
        return None
    return "/".join(parts[: min(depth, len(parts))])


def is_file_hub_node(node: dict) -> bool:
    """True when node label is the basename of source_file (file hub)."""
    source_file = node.get("source_file") or ""
    label = node.get("label") or ""
    if not source_file or not label:
        return False
    kind = node.get("kind")
    if kind == "file":
        return True
    if kind and kind != "file":
        return False
    return Path(normalize_source_path(source_file)).name == label
