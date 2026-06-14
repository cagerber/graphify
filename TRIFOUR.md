# Trifour fork delta (graphifyy)

Upstream: [safishamsi/graphify](https://github.com/safishamsi/graphify) (`v8` branch).

## Changes in `0.8.39+trifour.1`

- **`graphify/paths.py`** — single source of truth for `GRAPHIFY_OUT` (manifest, cache, memory, converted, scan skip dirs).
- **`detect.py`** — manifest load/save/incremental resolve paths at **call time** (no import-time `graphify-out/manifest.json` default).
- **`cache.py`**, **`watch.py`**, **`__main__.py`** — use `paths` instead of module-level env snapshots.

## ODS consumption

Pin in ODS `pyproject.toml`:

```toml
[dependency-groups]
dev = ["graphifyy", ...]

[tool.uv.sources]
graphifyy = { git = "https://github.com/cagerber/graphify.git", rev = "7b9b757" }
```

Set `GRAPHIFY_OUT=.local/graphify-out` in ODS `.env`; run via `dev/graphify` → `uv run graphify`.

## Not yet in this fork

- ObjectScript tree-sitter / regex extractor (`.cls` still mapped to Apex upstream).
- OpenRouter as a built-in provider (use `~/.graphify/providers.json` upstream).
- Shell hooks in `hooks.py` still reference literal `graphify-out/` paths.
