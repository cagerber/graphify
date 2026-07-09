"""Canonical graphify output paths (GRAPHIFY_OUT env).

All runtime resolution goes through here so import-time defaults do not
freeze ``graphify-out/`` when the env var is set later (e.g. ODS
``.local/graphify-out``).

Upstream #1423 symbols (``GRAPHIFY_OUT``, ``GRAPHIFY_OUT_NAME``, ``out_path``,
``default_graph_json``) are exposed via :func:`graphify_out_rel` and PEP 562
lazy attributes so env overrides remain call-time safe.
"""
from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

_DEFAULT_REL = "graphify-out"

# Directory segments that, when they appear as a whole path component, mark the
# whole path as a test location. Matched against path *segments* (not raw
# substrings) so "src/contest.py" / "latest/x.py" / "src/greatest/x.py" do NOT
# match — only a segment that *equals* one of these names (case-insensitively).
_TEST_DIR_SEGMENTS = frozenset({"tests", "test", "spec", "specs", "__tests__"})

# Filename patterns marking a file as a test, matched against the *filename*
# only (case-insensitive). These are conventions across ecosystems:
#   test_*.py            pytest / unittest
#   *_test.*             Go / Python / Rust
#   *.test.*             JS/TS (jest, vitest)
#   *.spec.* / *_spec.*  Jasmine / RSpec / Karma
#   *.Tests.ps1          PowerShell Pester
#   *Test.java / *Tests.cs (case-sensitive convention, handled below)
_TEST_FILENAME_PATTERNS = (
    re.compile(r"^test_.*", re.IGNORECASE),
    re.compile(r".*_test\..+$", re.IGNORECASE),
    re.compile(r".*\.test\..+$", re.IGNORECASE),
    re.compile(r".*\.spec\..+$", re.IGNORECASE),
    re.compile(r".*_spec\..+$", re.IGNORECASE),
    re.compile(r".*\.tests\.ps1$", re.IGNORECASE),
    re.compile(r".*Test\.java$"),
    re.compile(r".*Tests\.java$"),
    re.compile(r".*Tests\.cs$"),
)


def _is_test_path(path: str) -> bool:
    """Classify a source path as a test path (case-insensitive, segment-aware)."""
    if not path:
        return False
    norm = str(path).replace("\\", "/")
    pure = PurePosixPath(norm)
    for segment in pure.parts:
        if segment.lower() in _TEST_DIR_SEGMENTS:
            return True
    filename = pure.name
    if not filename:
        return False
    for pattern in _TEST_FILENAME_PATTERNS:
        if pattern.match(filename):
            return True
    return False


def _path_proximity_winner(call_site_file: str, candidate_files: dict[str, str]) -> str | None:
    """Pick the candidate whose source file is closest to the call site."""
    if not call_site_file:
        return None
    call_norm = str(call_site_file).replace("\\", "/")
    call_dir = PurePosixPath(call_norm).parent

    same_file = [cid for cid, f in candidate_files.items()
                 if str(f).replace("\\", "/") == call_norm]
    if len(same_file) == 1:
        return same_file[0]
    if len(same_file) > 1:
        return None

    same_dir = [cid for cid, f in candidate_files.items()
                if PurePosixPath(str(f).replace("\\", "/")).parent == call_dir]
    if len(same_dir) == 1:
        return same_dir[0]
    if len(same_dir) > 1:
        return None

    call_parts = call_dir.parts

    def _common_prefix_len(f: str) -> int:
        parts = PurePosixPath(str(f).replace("\\", "/")).parent.parts
        n = 0
        for a, b in zip(call_parts, parts):
            if a != b:
                break
            n += 1
        return n

    scored = sorted(
        ((cid, _common_prefix_len(f)) for cid, f in candidate_files.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    if not scored:
        return None
    best = scored[0][1]
    winners = [cid for cid, score in scored if score == best]
    if len(winners) == 1 and best > 0:
        return winners[0]
    return None


def disambiguate_ambiguous_candidates(
    candidates: list[str],
    candidate_files: dict[str, str],
    call_site_file: str,
) -> str | None:
    """Resolve an ambiguous bare-name call to one candidate, or ``None``."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    call_is_test = _is_test_path(call_site_file)
    test_cands = [c for c in candidates if _is_test_path(candidate_files.get(c, ""))]
    nontest_cands = [c for c in candidates if c not in set(test_cands)]

    if call_is_test:
        call_norm = str(call_site_file).replace("\\", "/")
        same_file_test = [
            c for c in test_cands
            if str(candidate_files.get(c, "")).replace("\\", "/") == call_norm
        ]
        if len(same_file_test) == 1:
            return same_file_test[0]
        if test_cands:
            survivors = test_cands
        else:
            survivors = nontest_cands or candidates
    else:
        survivors = nontest_cands

    if len(survivors) == 1:
        return survivors[0]
    if not survivors:
        return None

    return _path_proximity_winner(
        call_site_file,
        {c: candidate_files.get(c, "") for c in survivors},
    )


def graphify_out_rel() -> str:
    """Relative or absolute output directory from GRAPHIFY_OUT (default graphify-out)."""
    return os.environ.get("GRAPHIFY_OUT", _DEFAULT_REL)


def graphify_out_name() -> str:
    """Bare directory name even when GRAPHIFY_OUT is an absolute path."""
    return os.path.basename(os.path.normpath(graphify_out_rel()))


def graphify_out_dir(root: Path | str | None = None) -> Path:
    """Resolved output directory under *root* (or cwd when *root* is None)."""
    rel = graphify_out_rel()
    out = Path(rel)
    if out.is_absolute():
        return out
    base = Path(root).resolve() if root is not None else Path.cwd()
    return base / rel


def graphify_project_root(watch_path: Path | str | None = None) -> Path:
    """Repository root for resolving relative ``GRAPHIFY_OUT`` during subpath scans."""
    if watch_path is None:
        return Path.cwd().resolve()
    wp = Path(watch_path)
    if wp.is_absolute():
        return wp.resolve()
    return Path.cwd().resolve()


def graphify_out_for_watch(watch_path: Path | str | None = None) -> Path:
    """``GRAPHIFY_OUT`` anchored at :func:`graphify_project_root`, not the watch subfolder."""
    return graphify_out_dir(graphify_project_root(watch_path))


def out_path(*parts: str, root: Path | str | None = None) -> Path:
    """A path inside the configured output dir, e.g. ``out_path("cache")``."""
    return graphify_out_dir(root).joinpath(*parts)


def manifest_path(root: Path | str | None = None) -> str:
    return str(graphify_out_dir(root) / "manifest.json")


def default_graph_json_path(root: Path | str | None = None) -> str:
    return str(graphify_out_dir(root) / "graph.json")


def default_graph_json(root: Path | str | None = None) -> str:
    """Upstream alias for :func:`default_graph_json_path`."""
    return default_graph_json_path(root)


def skip_dir_names() -> frozenset[str]:
    """Directory basename(s) to skip when scanning source (includes GRAPHIFY_OUT tail)."""
    names = {_DEFAULT_REL}
    rel = graphify_out_rel()
    for part in Path(rel).parts:
        if part not in (".", ".."):
            names.add(part)
    return frozenset(names)


def __getattr__(name: str) -> object:
    if name == "GRAPHIFY_OUT":
        return graphify_out_rel()
    if name == "GRAPHIFY_OUT_NAME":
        return graphify_out_name()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
