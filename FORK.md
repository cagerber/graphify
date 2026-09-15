# Fork delta (graphifyy)

**Public repo.** This document is package-level only — no private consumer runbooks, application
paths or product names. Consumer integration docs live in the consuming repo.

Upstream: [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — default branch `v8`.
Base of this fork: tag **`v0.9.61`** (`fe66389`), i.e. this delta applies to upstream `v0.9.61` as-is.

Version scheme: **`<upstream version>+ext.<n>`** — a PEP 440 *local version segment*. `0.9.61-ext.1`
is not a legal version string (anything before the `+` parses as a pre-release marker, and `ext` is
not one); `0.9.61+ext-1` is legal in `pyproject.toml` and normalises to `0.9.61+ext.1` in built
metadata. The suffix stays because it is what distinguishes this build from a stock upstream release
of the same version: upstream namespaces the AST cache by the package version
(`cache/ast/v{version}-s{schema}/`), so a bare `0.9.61` would share cached extractor output with a
stock 0.9.61 run in the same tree. The exact revision is recorded by the consumer's lock file and by
PEP 610 `direct_url.json` for VCS installs.

## What this fork is

Not a patch set on upstream: it is a **host for consumer-defined extractors plus a configuration
layer**, for languages upstream does not speak. Upstream has no extractor-registration hook and maps
`.cls` to its Apex extractor ("Salesforce constructs"), which is the wrong language for a consumer
whose `.cls` files are something else entirely.

1. **Consumer extractor registry** — `[[tool.graphify.extractors]]` in the consumer's
   `pyproject.toml` names `module` / `function` / `extensions` / `path_glob`;
   `graphify.ext.extract.registry` resolves them per path *before* built-in suffix dispatch, and
   several rules may match one path (results are merged). Consumer-owned paths bypass the AST file
   cache, so a routing change can never be served a stale entry, and they no longer trip upstream's
   "no AST extractor" / zero-node warnings (`#1666`, `#1689`).
2. **Consumer-declared code extensions** — `detect.CODE_EXTENSIONS` is upstream's built-in set plus
   `graphify.config.consumer_code_extensions()`: the union of the suffixes named by the consumer's
   extractor rules, `[tool.graphify] code_extensions`, and the `GRAPHIFY_CODE_EXTENSIONS` override.
   A declared suffix with no rule match for a given path routes to a **stub** (no nodes + an
   actionable error) instead of being handed to another language's extractor. No product-specific
   extension list lives in this repository.
3. **Optional post-extract merge hook** — `[tool.graphify] post_extract_merge = "module:function"`,
   called after a code rebuild; the fork only imports the callable, it never names a consumer
   package. A missing/unimportable callable is a no-op, not a crash.
4. **Call-time output-directory resolution, anchored at the project root** — `GRAPHIFY_OUT` is read
   when paths are used, not at import, so an env var set after import still applies
   (`graphify.paths.graphify_out_dir` / `graphify_out_for_watch` / `graphify_out_rel`,
   `GRAPHIFY_OUT_NAME`); manifest, cache, memory, converted and scan-skip-dir paths all route
   through it, and a *relative* out dir with a subdirectory target (`graphify update src/BI`) writes
   to `<repo>/.local/graphify-out`, not `<target>/.local/graphify-out`. `skip_dir_names()` prunes
   only the configured out-dir name at top level, so a nested `graphify-out/nlp` cannot name-prune
   same-named source directories.
5. **`[tool.graphify]` configuration surface** — `test_roots`, `tests_covers`
   (`strip_prefix`, `strip_test_filename_prefix`, `collapse_tests_dir`), `folder_prefix_depth`,
   `folder_edges`, `folder_affinity`, `pytest_enrich`, `heuristic_labels`, `code_extensions`,
   `extractors`. Loader is `graphify/config.py`, cached per pyproject signature (extractor dispatch
   resolves it per file; re-parsing cost ~0.44 ms → ~0.011 ms).
6. **Enrichment and derived links** — `graphify/enrich.py` emits INFERRED `same_directory` /
   `shared_folder` folder links, pytest `metadata.markers`, and config-driven `tests_covers` edges;
   the post-build path runs enrich (and optionally heuristic relabelling) after `update` or a hook
   rebuild. The unchanged-topology check in the watch rebuild ignores these derived links: they are
   regenerated every build and carry no topology signal, and comparing them used to strand a missing
   `graph.html` (the pair a hub star-link occupies can already hold an import edge, so which survives
   depends on write order).
7. **Visualisation contract and layers** — `graphify/viz_contract.py` plus `graphify/ext/viz/*`
   (aggregate, expand, grouping, labels, load, communities, test hubs) build the interactive views;
   `graphify/viz_layers.py` adds the folder-affinity community edges and the
   `viz --test-files-only` file-hub layer; `GRAPHIFY_VIZ_NODE_LIMIT=0` is a kill switch that also
   removes a stale `graph.html` instead of leaving it behind.
8. **Heuristic labelling** — `graphify label --heuristic` names communities from path/symbol
   structure with no LLM call (`graphify/heuristic_labels.py`, `graphify/node_paths.py`).
9. **Node kinds** — `kind` on AST nodes (`file` / `class` / `function` / `method` / `other`) with
   `finalize_node_kinds()` wired into bulk Python extraction (`graphify/node_kind.py`).
10. **CLI and UX** — `graphify callers "<symbol>"` lists direct inbound call edges, and
    `graphify query "who calls X"` routes to it instead of a truncated community BFS; `main()` exits
    **130** on Ctrl+C rather than propagating a traceback; stale-skill warnings are scoped to the
    project's `.agents/skills/graphify` when `GRAPHIFY_OUT` is set (global `uv tool install`
    destinations are irrelevant to a project-scoped setup).
11. **Packaging** — the core install ships the common tree-sitter grammars (python/js/ts/go/rust/
    java/c/cpp/bash/json) and moves the rest to `langs-extra` or per-language extras that soft-fail
    when absent; `all` remains the union of every other extra.

## Where the code lives

Fork-only modules — conflict-free by construction, they cannot collide with an upstream merge:

| Path | Area |
|---|---|
| `graphify/config.py` | `[tool.graphify]` loader, extractor rules, consumer code extensions |
| `graphify/ext/extract/{registry,consumer,post}.py` | extractor registration, dispatch + stub, post-extract merge |
| `graphify/ext/query/callers.py` | direct-inbound-call resolution |
| `graphify/ext/skill_scope.py` | skill-version check scope policy |
| `graphify/enrich.py`, `heuristic_labels.py`, `node_kind.py`, `node_paths.py` | post-build enrich, heuristic labels, node kinds, path helpers |
| `graphify/viz_contract.py`, `viz_layers.py`, `graphify/ext/viz/*` | viz protocol, layers, builders |
| `scripts/upstream_footprint*.py/.txt` | fork-only guard rail (not wired into upstream CI) |
| `tests/test_{enrich,config_enrich,heuristic_labels,node_kind,skill_version_scope,viz_layers,cli_keyboard_interrupt}.py`, `tests/ext/*` | fork tests |

Fork code inside upstream-owned files is limited to the **hook points** themselves:

- `graphify/extract.py` — `_get_extractors()`, `_path_has_extractor()`, `_bypass_ast_cache()`,
  `_ast_progress_interval()` and the merge call sites that dispatch into the registry.
- `graphify/paths.py` — the call-time `GRAPHIFY_OUT` resolver family re-exported for upstream's
  existing call sites.

Nothing else: `graphify/serve.py` is byte-identical to upstream, and `watch.py`, `__main__.py`,
`cli.py`, `detect.py`, `cache.py` hold no fork-only function.

## Keeping it mergeable

**Rule: deltas inside upstream-owned files are additive and minimal.** Every deleted upstream line is
a line we no longer inherit, and rewriting upstream prose or formatting conflicts on the next merge
for no benefit. When a line must change, change the fewest lines and put a `Fork:` comment beside it
saying why — that comment is what makes the next merge a 30-second resolution instead of a
reconstruction. Fork-only CI is a script, never a step in upstream's `.github/workflows/ci.yml`.

Measure before merging:

```bash
python scripts/upstream_footprint.py          # per-file surface
python scripts/upstream_footprint.py --check  # exits 1 on rewritten upstream prose
```

Surface of this delta against `v0.9.61`: **35 fork-only files** and **19 upstream-owned files**
modified (`+792 / -152`), with zero rewritten upstream comments or docstrings (one waiver, recorded in
`scripts/upstream_footprint_allow.txt`: upstream's mojibake em dash inside the hook payload that is
installed into users' `.git/hooks`, which would otherwise ship corrupted bytes). The numbers come from
`scripts/upstream_footprint.py`, never from this prose — re-run it after any delta change. `ext.2`
added `graphify/install.py` (17 → 19) and `tests/test_install.py` to the surface.

Merge protocol: `uv.lock` is never hand-merged — take either side, then `uv lock`. After every merge,
re-check the upstream invariants this fork interacts with:

- `all` is the union of every other extra (upstream `tests/test_backend_extras.py`).
- The hook payloads in `hooks.py` stay self-contained — upstream's tests `exec` the root-resolution
  snippet with only `Path`/`os` in scope.
- Hidden `--out`-style plumbing: an upstream option added near a fork call site must survive the
  merge (an auto-merge once silently dropped upstream's `_out = os.environ.get(...)` line).
- Extractor dispatch sites (`_get_extractor` → `_get_extractors`) and the unclassified-file
  surfacing path, which upstream refactors periodically.

Then run the full suite: `env -u OPENAI_API_KEY -u GOOGLE_API_KEY -u GEMINI_API_KEY -u
ANTHROPIC_API_KEY -u OPENROUTER_API_KEY uv run pytest -q -p no:randomly`, plus `ruff check`.

## Upstreaming candidates

The generic half of this delta belongs upstream: consumer extractor registration, consumer-declared
code extensions, call-time `GRAPHIFY_OUT` resolution with project-root anchoring, folder-edge
enrichment, and heuristic community labelling. Each is useful without a consumer-specific language;
upstream merges are cheaper for us the more of this lands there.

## Consumer configuration (`pyproject.toml`)

```toml
[tool.graphify]
test_roots = ["tests"]
folder_prefix_depth = 2
folder_edges = true
folder_affinity = true
pytest_enrich = true
heuristic_labels = true
code_extensions = [".mylang"]              # suffixes that are code for this consumer
# Optional: run after a full AST rebuild
# post_extract_merge = "my_package.hooks:merge_graphify_result"

[[tool.graphify.tests_covers]]
test = "tests/**/test_*.py"
strip_prefix = "tests/"
strip_test_filename_prefix = "test_"
collapse_tests_dir = true

# Consumer-owned extractors (the module lives in the consumer repo):
# [[tool.graphify.extractors]]
# module = "my_package.extractors"
# function = "extract_custom"
# extensions = [".mylang"]
# path_glob = "src/**"        # omit to claim the suffix for every path
```

## Environment flags

| Variable | Default | Effect |
|----------|---------|--------|
| `GRAPHIFY_OUT` | `graphify-out` | Output directory (consumers typically use `.local/graphify-out`) |
| `GRAPHIFY_OUT_NAME` | `graphify-out` | Name used when resolving defaults |
| `GRAPHIFY_CODE_EXTENSIONS` | from `[tool.graphify]` | Extra code suffixes, comma/space separated |
| `GRAPHIFY_AST_PROGRESS_INTERVAL` | `1000` | AST progress log interval (large corpora) |
| `GRAPHIFY_FOLDER_EDGES` | `1` | `enrich` / post-`update` folder edges |
| `GRAPHIFY_FOLDER_AFFINITY` | `1` | Folder links in aggregated `graph.html` |
| `GRAPHIFY_PYTEST_ENRICH` | `1` | Pytest markers + `tests_covers` on `update` |
| `GRAPHIFY_HEURISTIC_LABELS` | from `[tool.graphify]` or `0` | Heuristic relabel after `update` |

**Deprecated CLI aliases:** `label-communities` → `label --heuristic`, `folder-edges` →
`enrich --folder-links`.

## Consumer git pin

```toml
[tool.uv.sources]
graphifyy = { git = "https://github.com/cagerber/graphify.git", rev = "<commit>" }
```

Set `GRAPHIFY_OUT` in the environment (e.g. `.local/graphify-out`); run via `uv run graphify`.

## Not yet in this fork

- OpenRouter as a built-in provider (upstream reads `~/.graphify/providers.json`).
