"""Heuristic community labels from source paths and symbols (no LLM)."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from graphify.node_paths import CODE_EXTENSIONS, SKIP_DIR_PARTS

_PLACEHOLDER_RE = re.compile(r"^Community \d+$", re.IGNORECASE)

_BORING_SYMBOLS = frozenset(
    {
        "Path",
        "str",
        "int",
        "bool",
        "None",
        "dict",
        "list",
        "set",
        "tuple",
        "Any",
        "Optional",
        "Union",
        "Callable",
        "Type",
        "Enum",
        "object",
        "Exception",
        "BaseModel",
        "Field",
        "self",
        "cls",
    }
)


def is_placeholder(label: str) -> bool:
    return bool(_PLACEHOLDER_RE.match((label or "").strip()))


def labels_mostly_generic(labels: dict[int, str], threshold: float = 0.85) -> bool:
    if not labels:
        return True
    generic = sum(1 for v in labels.values() if is_placeholder(v))
    return generic / len(labels) >= threshold


def _is_file_node_label(label: str) -> bool:
    if not label:
        return True
    lower = label.lower()
    return lower.endswith(CODE_EXTENSIONS)


def _path_prefix(source_file: str, depth: int = 3) -> tuple[str, ...] | None:
    normalized = source_file.replace("\\", "/").lstrip("./")
    if not normalized:
        return None
    parts = [
        part
        for part in Path(normalized).parts
        if part not in SKIP_DIR_PARTS and not part.startswith(".")
    ]
    if not parts:
        return None
    if len(parts) > 1 and parts[-1].lower().endswith(CODE_EXTENSIONS):
        parts = parts[:-1]
    if not parts:
        return None
    return tuple(parts[: min(depth, len(parts))])


def _format_prefix(prefix: tuple[str, ...]) -> str:
    return " / ".join(prefix)


def _truncate(name: str, limit: int = 56) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) <= limit:
        return name
    return name[: limit - 1].rstrip() + "…"


def heuristic_name(
    node_attrs: dict[str, dict],
    member_ids: list[str],
    cid: int,
) -> str:
    from graphify.trifour.viz.labels import heuristic_name as _heuristic_name_v2

    return _heuristic_name_v2(node_attrs, member_ids, cid)


def dedupe_labels(labels: dict[int, str]) -> dict[int, str]:
    seen: dict[str, int] = {}
    out: dict[int, str] = {}
    for cid in sorted(labels):
        name = labels[cid]
        if is_placeholder(name):
            out[cid] = name
            continue
        if name not in seen:
            seen[name] = cid
            out[cid] = name
        else:
            out[cid] = f"{name} (#{cid})"
    return out


def communities_from_nodes(nodes: list[dict]) -> dict[int, list[str]]:
    communities: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        cid = node.get("community")
        node_id = node.get("id")
        if cid is None or node_id is None:
            continue
        communities[int(cid)].append(str(node_id))
    return dict(communities)


def build_heuristic_labels(
    communities: dict[int, list[str]],
    node_attrs: dict[str, dict],
    *,
    force: bool = False,
    existing: dict[int, str] | None = None,
) -> dict[int, str]:
    existing = existing or {}
    labels: dict[int, str] = {}
    for cid, members in communities.items():
        prior = existing.get(cid, "")
        if prior and not is_placeholder(prior) and not force:
            labels[cid] = prior
        else:
            labels[cid] = heuristic_name(node_attrs, members, cid)
    return dedupe_labels(labels)


def patch_graph_json_nodes(graph_path: Path, labels: dict[int, str]) -> None:
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    for node in data.get("nodes", []):
        cid = node.get("community")
        if cid is None:
            continue
        node["community_name"] = labels.get(int(cid), f"Community {cid}")
    graph_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_heuristic_labels(
    out_dir: Path,
    *,
    project_root: Path | None = None,
    force: bool = False,
    if_generic: bool = False,
    skip_report: bool = False,
    skip_html: bool = False,
) -> dict[int, str]:
    graph_path = out_dir / "graph.json"
    labels_path = out_dir / ".graphify_labels.json"

    if not graph_path.is_file():
        raise FileNotFoundError(f"No graph.json at {graph_path}")

    data = json.loads(graph_path.read_text(encoding="utf-8"))
    communities = communities_from_nodes(data.get("nodes", []))
    existing: dict[int, str] = {}
    if labels_path.is_file():
        raw = json.loads(labels_path.read_text(encoding="utf-8"))
        existing = {int(k): str(v) for k, v in raw.items()}

    if if_generic and not force and not labels_mostly_generic(existing):
        return existing

    node_attrs = {str(n["id"]): n for n in data.get("nodes", []) if n.get("id")}
    labels = build_heuristic_labels(
        communities, node_attrs, force=force, existing=existing
    )

    labels_path.write_text(
        json.dumps({str(k): v for k, v in sorted(labels.items())}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    patch_graph_json_nodes(graph_path, labels)

    if not skip_report:
        _regenerate_report(out_dir, labels, graph_path, project_root)

    if not skip_html:
        from graphify.viz_layers import emit_default_html

        emit_default_html(out_dir, project_root=project_root)

    return labels


def _regenerate_report(
    out_dir: Path,
    labels: dict[int, str],
    graph_path: Path,
    project_root: Path | None,
) -> None:
    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import score_all
    from graphify.report import generate

    data = json.loads(graph_path.read_text(encoding="utf-8"))
    graph = build_from_json(data)
    communities = communities_from_nodes(data.get("nodes", []))
    cohesion = score_all(graph, communities)
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    questions = suggest_questions(graph, communities, labels)

    detect_path = out_dir / ".graphify_detect.json"
    if detect_path.is_file():
        detection = json.loads(detect_path.read_text(encoding="utf-8"))
        if "total_files" not in detection:
            detection = {"warning": "heuristic relabel — detection stats incomplete"}
    else:
        detection = {"warning": "heuristic relabel — detection file missing"}

    root_name = (project_root or Path(".")).resolve().name
    root_file = out_dir / ".graphify_root"
    if root_file.is_file():
        root_name = Path(root_file.read_text(encoding="utf-8").strip()).name or root_name

    built_at_commit = None
    for node in data.get("nodes", []):
        built_at_commit = node.get("built_at_commit")
        if built_at_commit:
            break

    report = generate(
        graph,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        {"input": 0, "output": 0},
        root_name,
        suggested_questions=questions,
        built_at_commit=built_at_commit,
    )
    (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
