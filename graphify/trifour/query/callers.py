"""Direct inbound-call queries ("who calls X").

Fork extension: the CLI's ``query`` router and its ``callers`` subcommand call
:func:`extract_callers_target` / :func:`direct_callers_text` instead of the
community BFS traversal. The graph helpers it needs (``_find_node``,
``find_node_ambiguity``) are imported lazily from ``graphify.serve`` so this
module stays importable without the server stack.
"""

from __future__ import annotations

import networkx as nx


CALL_RELATIONS: frozenset[str] = frozenset({
    "calls",
    "indirect_call",
    "calls_method",
})


def is_call_edge(data: dict) -> bool:
    rel = str(data.get("relation") or "").strip().lower()
    if rel in CALL_RELATIONS:
        return True
    return str(data.get("context") or "").strip().lower() == "call"


def extract_callers_target(question: str) -> str | None:
    """Return the callee symbol when *question* is a direct 'who calls X' ask.

    Falls through (None) for open architectural questions so the normal BFS
    path still runs. Keeps punctuation/path characters in the capture so node
    ids and dotted labels remain usable.
    """
    import re

    q = " ".join(str(question).strip().split())
    if not q:
        return None
    patterns = (
        r"(?i)^(?:who|what)\s+calls\s+(.+?)(?:\?|$)",
        r"(?i)^callers?\s+of\s+(.+?)(?:\?|$)",
        r"(?i)^(?:what|which)\s+(?:functions?|methods?|symbols?)\s+call\s+(.+?)(?:\?|$)",
    )
    for pat in patterns:
        m = re.search(pat, q)
        if m:
            target = m.group(1).strip().strip("\"'`")
            if target:
                return target
    return None


def direct_callers_text(G: nx.Graph, label: str, *, limit: int = 200) -> str:
    """List direct inbound call edges for *label* (no community BFS)."""
    from graphify.build import edge_data
    from graphify.serve import _find_node, find_node_ambiguity

    matches = _find_node(G, label)
    if not matches:
        return f"No node matching '{label}' found."
    rivals = find_node_ambiguity(G, label)
    if rivals:
        lines = [
            f"Ambiguous: '{label}' matches {len(rivals)} nodes in different files.",
        ]
        for rival in rivals:
            lines.append(f"  {G.nodes[rival].get('source_file') or rival}")
            lines.append(f"    id: {rival}")
        lines.append("Retry with the repo-relative path or the full node id.")
        return "\n".join(lines)

    nid = matches[0]
    d = G.nodes[nid]
    callers: list[tuple[str, dict]] = []
    if isinstance(G, (nx.DiGraph, nx.MultiDiGraph)):
        neighbor_pairs = [("in", nb) for nb in G.predecessors(nid)]
        neighbor_pairs.extend(("out", nb) for nb in G.successors(nid))
    else:
        neighbor_pairs = [("?", nb) for nb in G.neighbors(nid)]

    seen: set[tuple[str, str]] = set()
    for _hint, nb in neighbor_pairs:
        if G.has_edge(nb, nid):
            ed = edge_data(G, nb, nid)
        elif G.has_edge(nid, nb):
            ed = edge_data(G, nid, nb)
        else:
            continue
        if not is_call_edge(ed):
            continue
        # Inbound caller→callee: edge source is the neighbor.
        src = ed.get("_src", nb if G.has_edge(nb, nid) else nid)
        if src != nb:
            continue
        key = (nb, str(ed.get("relation") or "calls"))
        if key in seen:
            continue
        seen.add(key)
        callers.append((nb, ed))

    header = (
        f"Direct callers of {d.get('label', nid)} "
        f"(id={nid}; {len(callers)} caller edge(s))"
    )
    if not callers:
        return header + "\n\n(no inbound call edges)"
    callers.sort(
        key=lambda item: (
            -(G.degree(item[0]) if item[0] in G else 0),
            str(G.nodes[item[0]].get("label") or item[0]),
        )
    )
    lines = [header, ""]
    for nb, ed in callers[:limit]:
        rel = ed.get("relation") or "calls"
        conf = ed.get("confidence") or ""
        loc = ed.get("source_location") or ""
        sfile = ed.get("source_file") or G.nodes[nb].get("source_file") or ""
        at = f" {sfile}:{loc}" if loc else (f" {sfile}" if sfile else "")
        lines.append(
            f"  <-- {G.nodes[nb].get('label', nb)} [{rel}] [{conf}]{at}".rstrip()
        )
        lines.append(f"      id: {nb}")
    if len(callers) > limit:
        lines.append(f"  ... and {len(callers) - limit} more")
    return "\n".join(lines)

