# Trifour fork delta (graphifyy)

Upstream: [safishamsi/graphify](https://github.com/safishamsi/graphify) (`v8` branch).

## Changes in `0.8.39+trifour.6`

- **Subpath `update`** — relative ``GRAPHIFY_OUT`` resolves from the **project cwd** (``graphify_out_for_watch``), not the watch subdirectory, so ``graphify update reference/`` writes to ``<repo>/.local/graphify-out``.
- **Legacy ``.refcsp`` encoding** — ODS ``extract_csp`` decodes UTF-8 first, then **cp1252** (Windows/Studio export); documented in ``shared.kg_extract.extract_csp``.

## Changes in `0.8.39+trifour.5`

- **Consumer extractors** — ``[[tool.graphify.extractors]]`` in consumer ``pyproject.toml``; ``graphify.trifour.extract.registry`` routes matching paths before built-in suffix dispatch (ODS: ``src/BI/**/*.cls`` → ``extract_bi_cls``).
- **`graphify.trifour.extract.ods`** — thin plugins delegating to ``shared.kg_extract`` (``extract_bi_cls``, ``extract_dfi``; ``tools/`` on ``sys.path``).
- **Consumer extractor cache** — paths matched by ``[[tool.graphify.extractors]]`` bypass the AST file cache so routing changes (e.g. Apex → BI semantic) cannot serve stale entries.
- **``.dfi`` corpus scan** — ``*.DFI`` files are included in ``CODE_EXTENSIONS`` (ODS BI pivot/dashboard artefacts).

## Changes in `0.8.39+trifour.4`

- **Git hooks** — `post-commit` / `post-checkout` honour **`GRAPHIFY_OUT`** (no hardcoded `graphify-out/` skip paths or `.graphify_root` reads).
- **`[tool.graphify]` enrich flags** — `folder_edges`, `folder_affinity`, `pytest_enrich`, `heuristic_labels` (env `GRAPHIFY_*` overrides when set).
- **CLI aliases** — `label-communities` → `label --heuristic`; `folder-edges` → `enrich --folder-links` (deprecated; prefer fork subcommands).
- **Bundled skill** — version stamp matches **`0.8.39+trifour.4`** after `graphify install`.

## Changes in `0.8.39+trifour.3`

- **`kind` on AST nodes** — `file`, `class`, `function`, `method`, `other` (+ `finalize_node_kinds` on bulk extract).
- **`graphify label --heuristic`** — path/symbol community names without LLM (`graphify/heuristic_labels.py`).
- **`graphify enrich`** — INFERRED `same_directory` / `shared_folder` edges; pytest `metadata.markers` + config-driven `tests_covers` (`graphify/enrich.py`, `graphify/config.py`).
- **`graphify viz --test-files-only`** — `graph-tests.html` file-hub layer (`graphify/viz_layers.py`).
- **Aggregated `to_html`** — folder-affinity community edges when `GRAPHIFY_FOLDER_AFFINITY` ≠ `0`.
- **`update` post-build** — optional enrich + heuristic via env (`GRAPHIFY_FOLDER_EDGES`, `GRAPHIFY_PYTEST_ENRICH`, `GRAPHIFY_HEURISTIC_LABELS`).

## Changes in `0.8.39+trifour.2`

- **`cluster-only` / `label`** — write outputs via `graphify_out_dir(watch_path)` so `GRAPHIFY_OUT` matches read path.

## Changes in `0.8.39+trifour.1`

- **`graphify/paths.py`** — single source of truth for `GRAPHIFY_OUT` (manifest, cache, memory, converted, scan skip dirs).
- **`detect.py`** — manifest load/save/incremental resolve paths at **call time**.
- **`cache.py`**, **`watch.py`**, **`__main__.py`** — use `paths` instead of module-level env snapshots.

## Consumer configuration (`pyproject.toml`)

```toml
[tool.graphify]
test_roots = ["tools"]
folder_prefix_depth = 2
folder_edges = true
folder_affinity = true
pytest_enrich = true
heuristic_labels = true   # ODS / iris_connect: on by default in pyproject

[[tool.graphify.tests_covers]]
test = "tests/**/test_*.py"
strip_prefix = "tests/"
strip_test_filename_prefix = "test_"

# ODS layout example (tools/<tool>/tests/ → tools/<tool>/):
# [[tool.graphify.tests_covers]]
# test = "tools/**/tests/test_*.py"
# strip_prefix = ""
# collapse_tests_dir = true
```

## Environment flags

| Variable | Default | Effect |
|----------|---------|--------|
| `GRAPHIFY_OUT` | `graphify-out` | Output directory (use `.local/graphify-out` in consumers) |
| `GRAPHIFY_FOLDER_EDGES` | `1` | `enrich` / post-`update` folder edges |
| `GRAPHIFY_FOLDER_AFFINITY` | `1` | Folder links in aggregated `graph.html` |
| `GRAPHIFY_PYTEST_ENRICH` | `1` | Pytest markers + `tests_covers` on `update` |
| `GRAPHIFY_HEURISTIC_LABELS` | from `[tool.graphify]` or `0` | Heuristic relabel after `update` |

**Deprecated CLI aliases (remove from `dev/graphify` when on trifour.4+):** `label-communities`, `folder-edges` — use `label --heuristic` and `enrich --folder-links` directly.

## ODS / iris_connect consumption

```toml
[tool.uv.sources]
graphifyy = { git = "https://github.com/cagerber/graphify.git", rev = "<pin-after-release>" }
```

Set `GRAPHIFY_OUT=.local/graphify-out` in `.env`; run via `dev/graphify` → `uv run graphify`.

## Not yet in this fork

- ObjectScript BI extractor for ``src/BI/**/*.cls`` via consumer ``[[tool.graphify.extractors]]`` and ``shared.kg_extract`` (SSOT in ODS ``tools/shared/kg_extract/``).
- OpenRouter as a built-in provider (use `~/.graphify/providers.json` upstream).
