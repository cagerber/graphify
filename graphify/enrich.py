"""Post-build graph enrichment: folder links, pytest markers, tests_covers."""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from graphify.config import GraphifyConfig, enrich_flags, load_graphify_config, match_glob, production_path_for_test
from graphify.node_paths import is_file_hub_node, parent_directory, path_prefix

_EDGE_KEY = "links"
_PYTEST_MARK_RE = re.compile(
    r"@pytest\.mark\.([a-zA-Z0-9_]+)",
    re.MULTILINE,
)


def _is_test_path(source_file: str, roots: list[str]) -> bool:
    normalized = source_file.replace("\\", "/").lstrip("./")
    for root in roots:
        r = root.rstrip("/")
        if normalized == r or normalized.startswith(r + "/"):
            return True
    return False


def _edge_list(data: dict) -> list[dict]:
    if _EDGE_KEY in data:
        return data[_EDGE_KEY]
    if "edges" in data:
        data[_EDGE_KEY] = data.pop("edges")
        return data[_EDGE_KEY]
    data[_EDGE_KEY] = []
    return data[_EDGE_KEY]


def _existing_pairs(edges: list[dict]) -> set[tuple[str, str, str]]:
    pairs: set[tuple[str, str, str]] = set()
    for edge in edges:
        rel = edge.get("relation", "")
        src, tgt = edge.get("source"), edge.get("target")
        if not src or not tgt:
            continue
        pairs.add((src, tgt, rel))
        pairs.add((tgt, src, rel))
    return pairs


def _append_edge(
    edges: list[dict],
    existing: set[tuple[str, str, str]],
    *,
    source: str,
    target: str,
    relation: str,
    source_file: str,
    confidence: str = "INFERRED",
) -> bool:
    if (source, target, relation) in existing:
        return False
    edges.append(
        {
            "source": source,
            "target": target,
            "relation": relation,
            "confidence": confidence,
            "source_file": source_file,
        }
    )
    existing.add((source, target, relation))
    existing.add((target, source, relation))
    return True


def _star_edges_for_groups(
    groups: dict[str, list[str]],
    hub_meta: dict[str, dict],
    edges: list[dict],
    existing: set[tuple[str, str, str]],
    relation: str,
) -> int:
    added = 0
    for group_key in sorted(groups):
        node_ids = sorted(groups[group_key])
        if len(node_ids) < 2:
            continue
        hub_id = node_ids[0]
        hub_sf = hub_meta[hub_id].get("source_file") or group_key
        for other_id in node_ids[1:]:
            if _append_edge(
                edges,
                existing,
                source=hub_id,
                target=other_id,
                relation=relation,
                source_file=hub_sf,
            ):
                added += 1
    return added


def add_folder_edges(data: dict, *, prefix_depth: int = 2) -> dict[str, int]:
    """Mutate graph dict; return counts of edges added per relation."""
    nodes = data.get("nodes", [])
    edges = _edge_list(data)
    existing = _existing_pairs(edges)

    hubs: dict[str, dict] = {}
    by_parent: dict[str, list[str]] = defaultdict(list)
    by_prefix: dict[str, list[str]] = defaultdict(list)

    for node in nodes:
        node_id = node.get("id")
        source_file = node.get("source_file") or ""
        if not node_id or not source_file:
            continue
        if node.get("kind") and node.get("kind") != "file" and not is_file_hub_node(node):
            continue
        if not is_file_hub_node(node):
            continue
        hubs[str(node_id)] = node
        parent = parent_directory(source_file)
        if parent is not None:
            by_parent[parent].append(str(node_id))
        prefix = path_prefix(source_file, depth=prefix_depth)
        if prefix:
            by_prefix[prefix].append(str(node_id))

    counts = {
        "same_directory": _star_edges_for_groups(
            by_parent, hubs, edges, existing, "same_directory"
        ),
        "shared_folder": _star_edges_for_groups(
            by_prefix, hubs, edges, existing, "shared_folder"
        ),
    }
    return counts


def _pytest_markers_from_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return sorted(set(_PYTEST_MARK_RE.findall(text)))


def _production_path_for_test(
    test_path: str,
    config: GraphifyConfig,
) -> str | None:
    for rule in config.tests_covers:
        prod = production_path_for_test(test_path, rule)
        if prod:
            return prod
    return None


def _hub_by_source_file(nodes: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in nodes:
        if not is_file_hub_node(node):
            continue
        sf = (node.get("source_file") or "").replace("\\", "/").lstrip("./")
        if sf and node.get("id"):
            out[sf] = str(node["id"])
    return out


def add_pytest_metadata_and_covers(
    data: dict,
    *,
    project_root: Path,
    config: GraphifyConfig | None = None,
) -> dict[str, int]:
    """Record pytest markers on test file hubs; add tests_covers edges when configured."""
    config = config or load_graphify_config(project_root)
    nodes = data.get("nodes", [])
    edges = _edge_list(data)
    existing = _existing_pairs(edges)
    hub_by_sf = _hub_by_source_file(nodes)

    marker_files = 0
    covers_added = 0

    for node in nodes:
        if not is_file_hub_node(node):
            continue
        sf = (node.get("source_file") or "").replace("\\", "/").lstrip("./")
        if not _is_test_path(sf, config.test_roots):
            continue
        abs_path = project_root / sf
        if not abs_path.is_file():
            continue
        markers = _pytest_markers_from_file(abs_path)
        if markers:
            meta = node.setdefault("metadata", {})
            if isinstance(meta, dict):
                meta["markers"] = markers
                marker_files += 1

        if not config.tests_covers:
            continue
        prod_sf = _production_path_for_test(sf, config)
        if not prod_sf:
            continue
        prod_id = hub_by_sf.get(prod_sf)
        test_id = str(node.get("id"))
        if not prod_id or prod_id == test_id:
            continue
        if _append_edge(
            edges,
            existing,
            source=test_id,
            target=prod_id,
            relation="tests_covers",
            source_file=sf,
        ):
            covers_added += 1

    return {"marker_files": marker_files, "tests_covers": covers_added}


def community_folder_affinity(
    nodes: list[dict],
    structural_cross: set[tuple[int, int]],
    *,
    prefix_depth: int = 2,
) -> list[tuple[int, int, str, int]]:
    """Return (comm_a, comm_b, relation, weight) for folder-linked communities."""
    comm_parent: dict[int, Counter[str]] = defaultdict(Counter)
    comm_prefix: dict[int, Counter[str]] = defaultdict(Counter)

    for node in nodes:
        cid = node.get("community")
        source_file = node.get("source_file") or ""
        if cid is None or not source_file:
            continue
        cid = int(cid)
        parent = parent_directory(source_file)
        if parent is not None:
            comm_parent[cid][parent] += 1
        prefix = path_prefix(source_file, depth=prefix_depth)
        if prefix:
            comm_prefix[cid][prefix] += 1

    def dominant(counter: Counter[str]) -> str | None:
        if not counter:
            return None
        return counter.most_common(1)[0][0]

    by_parent: dict[str, list[int]] = defaultdict(list)
    for cid in comm_parent:
        dom = dominant(comm_parent[cid])
        if dom is not None:
            by_parent[dom].append(cid)

    by_prefix: dict[str, list[int]] = defaultdict(list)
    for cid in comm_prefix:
        dom = dominant(comm_prefix[cid])
        if dom is not None:
            by_prefix[dom].append(cid)

    affinity: list[tuple[int, int, str, int]] = []
    seen: set[tuple[int, int, str]] = set()

    def add_stars(groups: dict[str, list[int]], relation: str) -> None:
        for key in sorted(groups):
            cids = sorted(set(groups[key]))
            if len(cids) < 2:
                continue
            hub = cids[0]
            for other in cids[1:]:
                pair = (min(hub, other), max(hub, other))
                if pair in structural_cross:
                    continue
                token = (pair[0], pair[1], relation)
                if token in seen:
                    continue
                seen.add(token)
                affinity.append((pair[0], pair[1], relation, 1))

    add_stars(by_parent, "same_directory")
    add_stars(by_prefix, "shared_folder")
    return affinity


def apply_enrich(
    out_dir: Path,
    project_root: Path,
    *,
    folder_links: bool = True,
    pytest: bool = True,
    prefix_depth: int | None = None,
) -> dict[str, Any]:
    graph_path = out_dir / "graph.json"
    if not graph_path.is_file():
        raise FileNotFoundError(f"No graph.json at {graph_path}")

    config = load_graphify_config(project_root)
    depth = prefix_depth if prefix_depth is not None else config.folder_prefix_depth
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    counts: dict[str, Any] = {}

    if folder_links:
        counts.update(add_folder_edges(data, prefix_depth=depth))

    if pytest:
        counts.update(
            add_pytest_metadata_and_covers(data, project_root=project_root, config=config)
        )

    if any(
        counts.get(k, 0)
        for k in ("same_directory", "shared_folder", "tests_covers", "marker_files")
    ):
        graph_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return counts


def apply_post_build_enrich(out_dir: Path, project_root: Path) -> dict[str, Any]:
    """Optional post-update enrich + heuristic labels (``[tool.graphify]`` + env)."""
    result: dict[str, Any] = {}
    flags = enrich_flags(project_root)
    if flags["folder_edges"] or flags["pytest_enrich"]:
        result["enrich"] = apply_enrich(
            out_dir,
            project_root,
            folder_links=flags["folder_edges"],
            pytest=flags["pytest_enrich"],
        )
    if flags["heuristic_labels"]:
        from graphify.heuristic_labels import apply_heuristic_labels

        apply_heuristic_labels(
            out_dir,
            project_root=project_root,
            if_generic=True,
            skip_html=True,
        )
        result["heuristic_labels"] = True
    return result
