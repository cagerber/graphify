"""Consumer-extractor glue (fork side).

``[[tool.graphify.extractors]]`` rules can register more than one extractor for a
path; :func:`merge_extraction_results` concatenates their nodes/edges/errors and
:func:`extract_objectscript` is the generic built-in entry for consumer-owned
code (it delegates to the registry, and reports an actionable error when no rule
matches instead of silently extracting nothing).
"""

from __future__ import annotations

from pathlib import Path


def merge_extraction_results(results: list[dict]) -> dict:
    """Merge nodes/edges from multiple extractors; concatenate errors."""
    merged: dict = {"nodes": [], "edges": []}
    errors: list[str] = []
    for result in results:
        if not result:
            continue
        merged["nodes"].extend(result.get("nodes") or [])
        merged["edges"].extend(result.get("edges") or [])
        err = result.get("error")
        if err:
            errors.append(str(err))
    if errors:
        merged["error"] = "; ".join(errors)
    return merged




def is_consumer_owned_suffix(path: Path) -> bool:
    """True when the consumer declares *path*'s suffix as its own code.

    A suffix named by any ``[[tool.graphify.extractors]]`` rule (or listed in
    ``[tool.graphify] code_extensions``) belongs to the consumer even when no rule
    matches this particular path, so built-in extractors must not claim it.
    """
    from graphify.config import consumer_code_extensions

    suffix = path.suffix.lower()
    return bool(suffix) and suffix in consumer_code_extensions()


def extract_objectscript(path: Path) -> dict:
    """Extract ObjectScript via a consumer extractor when registered.

    Built-in ``.cls`` / routine dispatch only succeeds when the consumer
    registers an ObjectScript extractor under ``[[tool.graphify.extractors]]``.
    """
    try:
        from graphify.trifour.extract.registry import resolve_consumer_extractors

        extractors = resolve_consumer_extractors(path)
        if extractors:
            if len(extractors) == 1:
                return extractors[0](path)
            return merge_extraction_results([fn(path) for fn in extractors])
    except ImportError:
        pass
    return {
        "nodes": [],
        "edges": [],
        "error": "objectscript extractor unavailable (register [[tool.graphify.extractors]])",
    }


