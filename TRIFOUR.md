# Trifour fork delta (graphifyy)

**Public repo.** Changelog here is **package-level only** — no private consumer runbooks or application paths. Consumer integration docs live in the consuming repo.

Upstream: [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) (`v8` branch).

## Changes in `0.9.57+trifour.1`

- **Upstream merge 0.9.57** — 0.9.48→0.9.57: Robot Framework extractors (`.robot`/`.resource`), skipped-result manifest fix (#2879), skill-version warning names platform (#3144), `_reconcile_graph_html` for watch HTML, plus upstream fixes through 0.9.57.
- **Fork deltas preserved:**
  - `_path_has_extractor()` — consumer ``[[tool.graphify.extractors]]`` paths (e.g. `.refcsp`, `.dfi`) no longer trigger false **#1689** “no AST extractor” warnings or empty-node failure marks.
  - `GRAPHIFY_AST_PROGRESS_INTERVAL` default **1000** (large corpora).
  - ObjectScript dispatch (`.cls`/`.refcls`/routines) via consumer extractors, not Apex.
  - Trifour `CODE_EXTENSIONS` (`.refcls`, `.dfi`, `.refcsp`, routines).
  - `GRAPHIFY_OUT` skill-version check scoped to project `.agents/skills/graphify` only.
  - Post-build enrich hook in watch path.

## Changes in `0.9.47+trifour.6`

- **Upstream merge 0.9.47** — 150 commits (0.9.38→0.9.47 incl. v1.0.0-tagged work): `graph_path=` threading, mtime-coarse cache window, no-op-checkout hook guard, ocaml/commonlisp extras, Windows path fixes, new grammars. Upstream now lives at **Graphify-Labs/graphify** (org moved from safishamsi).
- **Merge-regression fixes (this release):**
  - `skip_dir_names()` prunes only the *top-level* configured-out name — nested parts (`graphify-out/nlp`) no longer name-prune same-named source dirs (#2273 preserved).
  - `GRAPHIFY_VIZ_NODE_LIMIT=0` kill switch now removes a stale `graph.html` (upstream raised; the fork's `emit_default_html` returns False).
  - `graphify_project_root()`: relative watch paths resolving inside cwd anchor at the project root (fork semantics); paths escaping cwd are their own root (#2316 manifest portability).
  - `graphify_out_rel()` precedence: env → explicitly-assigned module attr → default (monkeypatch-setattr teardown can otherwise shadow the env for the whole process).
  - `cache.py` re-exports `_GRAPHIFY_OUT` (upstream #1423 refactor dropped it).
  - `finalize_node_kinds()` is now wired into `extract_python` and infers `class` (PascalCase) — the node-kind feature (208fb78) was dead code after the merge.
  - `openai` added to the dev group (ollama/kimi/gemini backend tests import it).
  - Upstream watch/labeling tests adapted to fork anchoring; labeling batch-order assertion made hash-order independent.
- Upstream org moved `safishamsi/graphify` → `Graphify-Labs/graphify`; local `upstream` remote updated to match.

## Changes in `0.9.37+trifour.5`

- **Slimmer default deps** — keep core tree-sitter grammars (python/js/ts/go/rust/java/c/cpp/bash/json); move less-common grammars to optional ``langs-extra`` (soft-fail when absent).
- **``callers`` / ``who calls X``** — ``graphify callers "<symbol>"`` lists direct inbound call edges; ``graphify query "who calls X"`` routes to that mode instead of a truncated community BFS.

## Changes in `0.9.37+trifour.4`

- **Consumer-neutral extractors** — removed built-in product-specific extractor module; consumers register callables via ``[[tool.graphify.extractors]]`` (``module`` / ``function`` point at consumer code).
- **Config post-hook** — ``[tool.graphify] post_extract_merge = "module:function"`` (optional); fork only loads the callable, no hardcoded consumer packages.
- **ObjectScript dispatch** — built-in ``.cls`` / routine suffix map calls registered consumer extractors only (clear error when none registered).

## Changes in `0.9.37+trifour.3`

- **viz_layers** — import ``_viz_node_limit`` / ``to_html`` from ``graphify.exporters.html`` after upstream exporters split.

## Changes in `0.9.37+trifour.2`

- **Consumer post-hook** — ``merge_consumer_kg_extensions`` no-ops when the configured callable is missing or not importable.

## Changes in `0.9.37+trifour.1`

- **Upstream merge** — merged `safishamsi/graphify` `v8` @ `0.9.37` (`09a34ad`; ~300 commits past `9c27a52` / `0.9.12`).
- **Preserved Trifour** — call-time `GRAPHIFY_OUT` (`graphify.paths`), consumer extractors / multi-extractor dispatch, `viz_layers` / enrich post-build, project-scoped skill warnings when `GRAPHIFY_OUT` is set.
- **Adopted upstream** — update/watch failed-AST stamp clearing (#2543), NFC path helpers, `load_node_link_graph`, cluster-only write-beside `#1747`, incremental `gitignore=` detect plumbing, CLI/query/path/explain fixes through `0.9.37`.

## Changes in `0.9.12+trifour.1`

- **Upstream merge** — merged `safishamsi/graphify` `v8` @ `0.9.12` (`9c27a52`; 248 commits past `ad6cb75`).
- **Architecture** — upstream `extractors/` / `exporters/` / `cli.py` refactor integrated; Trifour deltas preserved.
- **Trifour preserved** — `graphify.trifour.*`, consumer extractors via `resolve_consumer_extractors`, call-time `GRAPHIFY_OUT`, `viz_contract`, `enrich` / `label --heuristic` / `viz` CLI, skill version scope when `GRAPHIFY_OUT` set.

## Changes in `0.8.46+trifour.8`

- **Upstream merge** — merged `safishamsi/graphify` `v8` @ `0.8.46` (incremental update, manifest, query perf, #1423 `GRAPHIFY_OUT` centralization).
- **Call-time `GRAPHIFY_OUT`** — `graphify.paths` keeps call-time resolution via PEP 562 lazy exports; upstream path helpers adapted, not replaced.
- **Package manifest extractor** — upstream `#1377` `extract_package_manifest` preserved alongside Trifour consumer extractors.

## Changes in `0.8.39+trifour.7`

- **Consumer ObjectScript routing** — built-in dispatch for ``.cls``, ``.refcls``, ``.mac``, ``.int``, ``.os``, ``.rtn`` through ``extract_objectscript`` (consumer-registered extractors).
- **Consumer extractor registry** — ``[[tool.graphify.extractors]]`` in consumer ``pyproject.toml``; cache bypass for consumer routes preserved.
- **Skill version scope** — stale-skill warnings respect project-only skill paths when ``GRAPHIFY_OUT`` is set (tests in ``tests/test_skill_version_scope.py``).

## Changes in `0.8.39+trifour.6`

- **Subpath `update`** — relative ``GRAPHIFY_OUT`` resolves from the **project cwd** (``graphify_out_for_watch``), not the watch subdirectory, so ``graphify update reference/`` writes to ``<repo>/.local/graphify-out``.
- **Skill version warnings** — when ``GRAPHIFY_OUT`` is set, stale-skill checks target **project** ``.agents/skills/graphify`` only (not global install paths from ``uv tool install``).

## Changes in `0.8.39+trifour.5`

- **Consumer extractors** — ``[[tool.graphify.extractors]]`` in consumer ``pyproject.toml``; ``graphify.trifour.extract.registry`` routes matching paths before built-in suffix dispatch.
- **Consumer extractor cache** — paths matched by ``[[tool.graphify.extractors]]`` bypass the AST file cache so routing changes cannot serve stale entries.
- **``.dfi`` corpus scan** — ``*.DFI`` files included in ``CODE_EXTENSIONS``.

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
test_roots = ["tests"]
folder_prefix_depth = 2
folder_edges = true
folder_affinity = true
pytest_enrich = true
heuristic_labels = true
# Optional: after full AST rebuild, call consumer merge hook
# post_extract_merge = "my_package.hooks:merge_graphify_result"

[[tool.graphify.tests_covers]]
test = "tests/**/test_*.py"
strip_prefix = "tests/"
strip_test_filename_prefix = "test_"

# Consumer-owned extractors (module lives in the consumer repo):
# [[tool.graphify.extractors]]
# module = "my_package.extractors"
# function = "extract_custom"
# extensions = [".cls"]
# path_glob = "src/**"
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

## Consumer git pin

```toml
[tool.uv.sources]
graphifyy = { git = "https://github.com/cagerber/graphify.git", rev = "<pin-after-release>" }
```

Set `GRAPHIFY_OUT` in the environment (e.g. `.local/graphify-out`); run via `uv run graphify`.

## Not yet in this fork

- OpenRouter as a built-in provider (use `~/.graphify/providers.json` upstream).
