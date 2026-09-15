"""Heuristic community labels v2 (no LLM)."""

from __future__ import annotations

from collections import Counter

from graphify.heuristic_labels import (
    _BORING_SYMBOLS,
    _format_prefix,
    _is_file_node_label,
    _path_prefix,
    _truncate,
)

_TEST_ROOT_MARKERS = ("tests/", "test/")


def _dominant_kind(node_attrs: dict[str, dict], member_ids: list[str]) -> str | None:
    counter: Counter[str] = Counter()
    for nid in member_ids:
        data = node_attrs.get(nid)
        if not data:
            continue
        kind = str(data.get("kind") or "").strip()
        if kind:
            counter[kind] += 1
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _package_segment(label: str, source_file: str) -> str | None:
    if label and "." in label and not label.startswith("."):
        parts = label.split(".")
        if len(parts) >= 2 and parts[0][0].isupper():
            return ".".join(parts[: min(3, len(parts))])
    normalized = source_file.replace("\\", "/")
    if "tools/" in normalized:
        idx = normalized.index("tools/")
        rest = normalized[idx:].split("/")
        if len(rest) >= +2:
            return "/".join(rest[:3])
    return None


def heuristic_name(
    node_attrs: dict[str, dict],
    member_ids: list[str],
    cid: int,
) -> str:
    """Enhanced heuristic naming (kind, package, relations)."""
    prefix_counter: Counter[tuple[str, ...]] = Counter()
    symbol_counter: Counter[str] = Counter()
    relation_counter: Counter[str] = Counter()
    test_heavy = 0

    for nid in member_ids:
        data = node_attrs.get(nid)
        if not data:
            continue
        source_file = str(data.get("source_file") or "")
        prefix = _path_prefix(source_file)
        if prefix:
            prefix_counter[prefix] += 1
        sf_norm = source_file.replace("\\", "/").lower()
        if any(m in sf_norm for m in _TEST_ROOT_MARKERS):
            test_heavy += 1
        label = (data.get("label") or "").strip()
        if label and not _is_file_node_label(label):
            symbol = label.rstrip("()").split(".")[-1]
            if len(symbol) > 2 and symbol not in _BORING_SYMBOLS:
                symbol_counter[symbol] += 1
        rel = str(data.get("relation") or "").strip()
        if rel:
            relation_counter[rel] += 1

    member_count = len(member_ids)
    dominant_kind = _dominant_kind(node_attrs, member_ids)

    if prefix_counter:
        best_prefix, best_count = prefix_counter.most_common(1)[0]
        if best_count >= max(2, int(member_count * 0.2)) or (
            member_count <= 5 and best_count >= 1
        ):
            name = _format_prefix(best_prefix)
            if test_heavy >= max(2, member_count // 2):
                name = f"tests · {name}"
            elif dominant_kind and dominant_kind not in ("file", "unknown"):
                name = f"{dominant_kind} · {name}"
            if symbol_counter and member_count <= 12:
                top_sym = symbol_counter.most_common(1)[0][0]
                name = f"{name} · {top_sym}"
            return _truncate(name)

    if symbol_counter:
        top = [sym for sym, _ in symbol_counter.most_common(2)]
        name = " · ".join(top)
        if dominant_kind:
            name = f"{dominant_kind} · {name}"
        return _truncate(name)

    if prefix_counter:
        name = _format_prefix(prefix_counter.most_common(1)[0][0])
        if relation_counter:
            top_rel = relation_counter.most_common(1)[0][0].replace("_", " ")
            name = f"{top_rel} · {name}"
        return _truncate(name)

    return f"Community {cid}"
