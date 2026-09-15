"""Post-extract merge hook — optional consumer callable from ``[tool.graphify]``.

Configure in the consumer ``pyproject.toml``:

```toml
[tool.graphify]
post_extract_merge = "my_package.hooks:merge_graphify_result"
```

The callable signature is::

    def merge_graphify_result(
        result: dict,
        *,
        project_root: Path,
        full_rebuild: bool,
    ) -> dict: ...

When unset or not importable, extraction results are returned unchanged.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from graphify.config import load_graphify_config


def _load_merge_callable(spec: str):
    module_name, _, func_name = spec.partition(":")
    module_name = module_name.strip()
    func_name = func_name.strip()
    if not module_name or not func_name:
        raise ImportError(
            f"post_extract_merge must be 'module:function', got {spec!r}"
        )
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name, None)
    if fn is None or not callable(fn):
        raise ImportError(f"post_extract_merge {spec!r} is not callable")
    return fn


def merge_consumer_kg_extensions(
    result: dict[str, Any],
    *,
    project_root: Path,
    full_rebuild: bool,
) -> dict[str, Any]:
    """
    On full corpus rebuild, optionally merge consumer-provided extensions.

    Incremental rebuilds skip the hook (refreshed on next full ``graphify update .``).
    """
    if not full_rebuild:
        return result

    cfg = load_graphify_config(project_root)
    spec = (cfg.post_extract_merge or "").strip()
    if not spec:
        return result

    try:
        merge_fn = _load_merge_callable(spec)
    except ImportError:
        return result

    return merge_fn(
        result,
        project_root=project_root,
        full_rebuild=full_rebuild,
    )
