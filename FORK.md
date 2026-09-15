# Fork delta (graphifyy)

**Public repo.** Changelog here is **package-level only** — no private consumer runbooks or application paths. Consumer integration docs live in the consuming repo.

Upstream: [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) (`v8` branch).

Version scheme: `<upstream version>+ext.<n>` (PEP 440 local segment; `-ext` is not a legal
version string). Headings below `0.9.61+ext.1` keep the historical `+trifour.N` strings they
were released under.

## Changes in `0.9.61+ext.1`

- **Local version suffix renamed** `+trifour.N` → `+ext.N` (generic; `-ext` is not a legal PEP 440
  version, so the local-segment spelling is used). Brand references are gone from code comments,
  docstrings, test names and this changelog; `TRIFOUR.md` is now `FORK.md`.
- **Fork code moved out of upstream-owned files** (all five of these were fork-only functions or
  product data living inside upstream modules):
  - the direct-inbound-call feature (`_direct_callers_text`, `_extract_callers_target`,
    `_is_call_edge`, `_CALL_RELATIONS`) → `graphify/trifour/query/callers.py`; `graphify/serve.py`
    is now byte-identical to upstream;
  - `extract_objectscript` / `_merge_extraction_results` → `graphify/trifour/extract/consumer.py`;
  - the skill-version scope policy → `graphify/trifour/skill_scope.py`;
  - the derived-folder-link filter → `graphify/enrich.py::topology_for_compare` (the concept it
    belongs to); `graphify/watch.py` holds no fork-only function any more.
- **Code extensions are consumer-declared data, not a fork constant.** `detect.CODE_EXTENSIONS` is
  now built-ins ∪ `graphify.config.consumer_code_extensions()` — the union of every suffix named by
  the consumer's `[[tool.graphify.extractors]]` rules, plus `[tool.graphify] code_extensions` and an
  optional `GRAPHIFY_CODE_EXTENSIONS` env override. The hardcoded fork list
  (`.refcls .dfi .refcsp .mac .int .os .rtn`) and the `.cls` suffix-map override are **gone**: the
  built-in table is upstream's (`.cls` → Apex), and a suffix the consumer declares but no rule
  matches for that path now routes to the consumer stub (no nodes + an actionable error) instead of
  being handed to another language's extractor.
- **`load_graphify_config()` is cached per pyproject signature** — extractor dispatch resolves it per
  file, and re-parsing cost ~0.44 ms/file (now ~0.011 ms).
- Fork-only files: 27 in the graphify package + 2 scripts. Upstream-owned files carry no fork-only
  function except `paths.py`'s call-time `GRAPHIFY_OUT` resolver family and four dispatcher helpers
  in `extract.py` (`_get_extractors`, `_path_has_extractor`, `_bypass_ast_cache`,
  `_ast_progress_interval`) — those *are* the hook points.

## Changes in `0.9.61+trifour.1`

- **Upstream merge 0.9.61** — 0.9.58→0.9.61 (57 commits): nested-function/namespace-package/sibling-import resolution fixes, Python symbol-resolution memoization (~47% faster), incremental-merge node preservation (#3477), process-pool fallback (#3497), hook rebuild root kept inside the repo (#3265: symlink-loop and out-of-repo `.graphify_root` are ignored), snap-confined uv-tool probing and the rotating-interpreter-prefix guard for the hook's python pin, Windows `os.replace` fallback (#3508), catch-up cross-file merge (#3490), C# generic call sites, unclassified-file surfacing in the watch/update rebuild path (#3511), and `graphify.serve` importing cleanly on 3.12/3.13 (`chinese` extra now pins `jieba-py`).
- **Merge-regression fixes (this release):**
  - `hooks.py` rebuild bodies: the auto-merge kept the fork's `graphify_out_dir(_root)` but dropped upstream's `_out = os.environ.get('GRAPHIFY_OUT', 'graphify-out')` line, leaving a latent `NameError` in the memory-lessons block and breaking the shipped-snippet tests (`upstream/tests/test_hooks.py` exec's the root-resolution snippet with only `Path`/`os`, so it must stay self-contained). Both bodies now use upstream's env read.
  - `[all]` is once again the union of every other extra: the slim-core split moved the less-common grammars into `langs-extra`, so they are listed in `all` explicitly (enforced by upstream's new `tests/test_backend_extras.py`).
- **Fork work taken back off the stash (stashed uncommitted, never released):**
  - `extract()` **Phase 1** now queues consumer-owned paths via `_get_extractors()` instead of `_get_extractor()`, so consumer-only files (`.refcsp`, `.dfi`, …) are no longer empty-slotted with false **#1666** zero-node warnings — the Phase-1 half of the trifour.2 worker fix.
  - `main()` exits **130** on Ctrl+C instead of propagating a traceback; `tests/test_labeling.py`'s interrupt test asserts the exit code and keeps its repairability invariant (`tests/test_cli_keyboard_interrupt.py`).
- **Fixed (pre-existing fork bug the merge surfaced):** `tests/test_watch.py::test_rebuild_code_keeps_a_visualization_when_over_the_viz_cap` was red before this merge too. The folder-edge enrich (`graphify/enrich.py`) made an incremental rebuild and a full rebuild disagree about a `same_directory` link — on an undirected graph the pair a hub star-link occupies can already hold an import edge, so which of the two survives depends on write order. `_rebuild_code`'s unchanged-topology check compared those derived links and saw a phantom change, so a missing `graph.html` was never repaired (it fell through to a re-cluster instead). The compare now runs through `_topology_for_compare()`, which drops enrich-generated `same_directory` / `shared_folder` links from both sides: they are regenerated on every build and carry no topology signal. Full suite green (5663 passed).

## Changes in `0.9.57+trifour.2`

- **Consumer-only extractors in parallel/sequential workers** — ``_extract_single_file`` / sequential fallback no longer return empty when built-in ``_get_extractor`` is ``None`` but ``[[tool.graphify.extractors]]`` owns the path (fixes false **#1666** for ``.refcsp`` / consumer fragments under ``ProcessPoolExecutor``).

## Changes in `0.9.57+trifour.1`

- **Upstream merge 0.9.57** — 0.9.48→0.9.57: Robot Framework extractors (`.robot`/`.resource`), skipped-result manifest fix (#2879), skill-version warning names platform (#3144), `_reconcile_graph_html` for watch HTML, plus upstream fixes through 0.9.57.
- **Fork deltas preserved:**
  - `_path_has_extractor()` — consumer ``[[tool.graphify.extractors]]`` paths (e.g. `.refcsp`, `.dfi`) no longer trigger false **#1689** “no AST extractor” warnings or empty-node failure marks.
  - `GRAPHIFY_AST_PROGRESS_INTERVAL` default **1000** (large corpora).
  - ObjectScript dispatch (`.cls`/`.refcls`/routines) via consumer extractors, not Apex.
  - Fork `CODE_EXTENSIONS` (`.refcls`, `.dfi`, `.refcsp`, routines).
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
- **Preserved fork deltas** — call-time `GRAPHIFY_OUT` (`graphify.paths`), consumer extractors / multi-extractor dispatch, `viz_layers` / enrich post-build, project-scoped skill warnings when `GRAPHIFY_OUT` is set.
- **Adopted upstream** — update/watch failed-AST stamp clearing (#2543), NFC path helpers, `load_node_link_graph`, cluster-only write-beside `#1747`, incremental `gitignore=` detect plumbing, CLI/query/path/explain fixes through `0.9.37`.

## Changes in `0.9.12+trifour.1`

- **Upstream merge** — merged `safishamsi/graphify` `v8` @ `0.9.12` (`9c27a52`; 248 commits past `ad6cb75`).
- **Architecture** — upstream `extractors/` / `exporters/` / `cli.py` refactor integrated; fork deltas preserved.
- **Preserved** — `graphify.trifour.*`, consumer extractors via `resolve_consumer_extractors`, call-time `GRAPHIFY_OUT`, `viz_contract`, `enrich` / `label --heuristic` / `viz` CLI, skill version scope when `GRAPHIFY_OUT` set.

## Changes in `0.8.46+trifour.8`

- **Upstream merge** — merged `safishamsi/graphify` `v8` @ `0.8.46` (incremental update, manifest, query perf, #1423 `GRAPHIFY_OUT` centralization).
- **Call-time `GRAPHIFY_OUT`** — `graphify.paths` keeps call-time resolution via PEP 562 lazy exports; upstream path helpers adapted, not replaced.
- **Package manifest extractor** — upstream `#1377` `extract_package_manifest` preserved alongside fork consumer extractors.

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

## Fork hygiene — footprint on upstream

**Rule: deltas inside upstream-owned files are additive and minimal.** Every deleted upstream
line is a line we no longer inherit, and a rewrite of upstream's prose or formatting conflicts
on the next merge for no benefit. Fork-only modules are free — they cannot conflict.

Measure before requesting a merge:

```bash
python scripts/upstream_footprint.py          # per-file surface
python scripts/upstream_footprint.py --check  # exits 1 on rewritten upstream prose
```

Surface after the 0.9.61 merge + this hygiene pass: **29 fork-only files (+2787 lines,
conflict-free)** against **18 upstream-owned files at +908 / −136** — down from +918 / −257,
with `graphify/paths.py` alone going from −92 to −6. Zero rewritten upstream
comments/docstrings; the single waiver (`scripts/upstream_footprint_allow.txt`) is upstream's
mojibake em dash inside the installed hook payload, which would otherwise ship to users.

When a line must change, change the fewest lines and add a `Fork:` comment beside it
saying why: that comment is what turns the next merge into a 30-second resolution instead of a
reconstruction. Fork-only CI is a script, not a step in upstream's
`.github/workflows/ci.yml`.

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

**Deprecated CLI aliases (remove from `dev/graphify` when on ext.4+):** `label-communities`, `folder-edges` — use `label --heuristic` and `enrich --folder-links` directly.

## Consumer git pin

```toml
[tool.uv.sources]
graphifyy = { git = "https://github.com/cagerber/graphify.git", rev = "<pin-after-release>" }
```

Set `GRAPHIFY_OUT` in the environment (e.g. `.local/graphify-out`); run via `uv run graphify`.

## Not yet in this fork

- OpenRouter as a built-in provider (use `~/.graphify/providers.json` upstream).
