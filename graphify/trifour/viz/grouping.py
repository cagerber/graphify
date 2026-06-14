"""Multi-perspective grouping for graphify nodes."""

from __future__ import annotations

from pathlib import Path

from graphify.node_paths import SKIP_DIR_PARTS
from graphify.trifour.viz.labels import heuristic_name
from graphify.viz_contract import GraphDocument

_VALID_DIMENSIONS = frozenset(
    {
        "detected_community",
        "path_prefix",
        "node_kind",
        "file_type",
    }
)


def _path_prefix_group(source_file: str, depth: int) -> str:
    normalized = source_file.replace("\\", "/").lstrip("./")
    if not normalized:
        return "unknown"
    parts = [
        part
        for part in Path(normalized).parts
        if part not in SKIP_DIR_PARTS and not part.startswith(".")
    ]
    if not parts:
        return "unknown"
    if len(parts) > 1 and "." in parts[-1]:
        parts = parts[:-1]
    if not parts:
        return "unknown"
    return "/".join(parts[: min(depth, len(parts))])


def group_ids(
    doc: GraphDocument,
    *,
    dimension: str,
    path_prefix_depth: int = 2,
) -> dict[str, int]:
    dim = (dimension or "detected_community").strip()
    if dim not in _VALID_DIMENSIONS:
        raise ValueError(
            f"unknown colorDimension: {dim!r}; valid: {sorted(_VALID_DIMENSIONS)}"
        )

    out: dict[str, int] = {}
    next_id = 0
    token_to_id: dict[str, int] = {}

    for node in doc["nodes"]:
        nid = node.get("id")
        if nid is None:
            continue
        nid_s = str(nid)

        if dim == "detected_community":
            if str(node.get("kind") or "") == "community":
                cid = node.get("community")
                if cid is not None:
                    out[nid_s] = int(cid)
                    continue
            cid = node.get("community")
            if cid is None:
                token = "none"
            else:
                token = str(int(cid))
        elif dim == "path_prefix":
            token = _path_prefix_group(
                str(node.get("source_file") or ""), path_prefix_depth
            )
        elif dim == "node_kind":
            token = str(node.get("kind") or "unknown")
        else:
            token = str(node.get("file_type") or "unknown")

        if token not in token_to_id:
            token_to_id[token] = next_id
            next_id += 1
        out[nid_s] = token_to_id[token]

    return out


def label_group(
    doc: GraphDocument,
    group_id: str,
    member_ids: list[str],
    *,
    labels: dict[int, str] | None = None,
    dimension: str = "detected_community",
) -> str:
    dim = (dimension or "detected_community").strip()
    if dim == "detected_community" and labels is not None:
        try:
            cid = int(group_id)
            if cid in labels:
                return labels[cid]
        except ValueError:
            pass

    node_attrs = {str(n["id"]): n for n in doc["nodes"] if n.get("id")}
    try:
        cid = int(group_id)
    except ValueError:
        cid = 0
    return heuristic_name(node_attrs, member_ids, cid)
