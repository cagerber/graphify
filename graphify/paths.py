"""Canonical graphify output paths (GRAPHIFY_OUT env).

All runtime resolution goes through here so import-time defaults do not
freeze ``graphify-out/`` when the env var is set later (e.g. ODS
``.local/graphify-out``).

Upstream #1423 symbols (``GRAPHIFY_OUT``, ``GRAPHIFY_OUT_NAME``, ``out_path``,
``default_graph_json``) are exposed via :func:`graphify_out_rel` and PEP 562
lazy attributes so env overrides remain call-time safe.
"""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from pathlib import Path, PurePosixPath

_DEFAULT_REL = "graphify-out"


def _atomic_replace(path: "str | Path", write_fn) -> None:
    """Atomically replace ``path`` with content written by ``write_fn(f)``.

    Writes a temp file in the SAME directory, then ``os.replace``s it into place
    (an atomic rename on one filesystem). A process kill (SIGKILL/Ctrl-C), OOM, or
    ENOSPC mid-write leaves the previous file intact — the destination is
    untouched until the rename. This is NOT a power-loss durability guarantee:
    there is no fsync (matching the rest of the codebase), so an OS/hardware crash
    right after the rename can still expose unflushed bytes on some filesystems.
    The temp file is removed if the write fails.

    A symlinked destination is resolved first so the write goes THROUGH the link
    to its target (rather than replacing the link with a regular file), keeping
    the shared-output/worktree symlink setups this module documents working.
    """
    # Resolve symlinks so the temp lands on the target's filesystem (same-fs
    # atomic rename) and the replace writes through the link, not over it.
    real = Path(os.path.realpath(str(path)))
    real.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(real.parent), prefix=f".{real.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            write_fn(f)
        # mkstemp creates the temp file 0600; match the destination's existing
        # mode (or the umask default for a new file) so an atomic replace never
        # silently tightens a previously group/world-readable output to
        # owner-only. Best-effort — a chmod failure must not fail the write.
        try:
            mode = stat.S_IMODE(os.stat(real).st_mode)
        except OSError:
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        try:
            os.chmod(tmp, mode)
        except OSError:
            pass
        try:
            os.replace(tmp, str(real))
        except PermissionError:
            # Windows: os.replace fails (WinError 5/32) when the destination is
            # briefly locked by another handle (antivirus, an open reader). Fall
            # back to copy-then-delete, matching graphify.cache's atomic writer.
            import shutil
            shutil.copy2(tmp, str(real))
            os.unlink(tmp)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_text_atomic(path: "str | Path", text: str) -> None:
    """Atomically write ``text`` (UTF-8) to ``path``. See :func:`_atomic_replace`."""
    _atomic_replace(path, lambda f: f.write(text))


def write_json_atomic(path: "str | Path", obj, *, indent: "int | None" = None, ensure_ascii: bool = True) -> None:
    """Atomically write ``obj`` as JSON to ``path``, streaming the encode into the
    temp file rather than materializing the whole string first (matters for very
    large graphs). ``ensure_ascii`` mirrors ``json.dump`` so callers that emit raw
    UTF-8 (non-ASCII labels/paths) keep byte-for-byte output. See :func:`_atomic_replace`."""
    _atomic_replace(path, lambda f: json.dump(obj, f, indent=indent, ensure_ascii=ensure_ascii))

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
    """Package-wide fallback so a ``GRAPHIFY_OUT`` override is honoured (#1423)."""
    return default_graph_json_path(root)


def skip_dir_names() -> frozenset[str]:
    """Directory basename(s) to skip when scanning source (includes GRAPHIFY_OUT tail)."""
    names = {_DEFAULT_REL}
    rel = graphify_out_rel()
    for part in Path(rel).parts:
        if part not in (".", ".."):
            names.add(part)
    return frozenset(names)


def nfc(s: str) -> str:
    """NFC-normalize a path string.

    macOS (HFS+/APFS) reports filenames in NFD while manifests, graph
    ``source_file`` entries and user input are typically NFC. Comparing raw
    strings makes the same file look like two different paths, so any path
    membership test must normalize BOTH sides (#2210, #2221/#2224).
    """
    import unicodedata
    return unicodedata.normalize("NFC", s)


def load_node_link_graph(path_or_data):
    """Load a graphify graph.json into a networkx graph, accepting both writers.

    The clustered writer stores edges under ``links`` (networkx's node-link
    default); the raw ``--no-cluster`` writer stores them under ``edges``.
    Consumers that call ``node_link_graph(data, edges="links")`` directly
    raise ``KeyError: 'links'`` on a raw graph (#2212) — the ``except
    TypeError`` fallback only covers old networkx without the ``edges``
    kwarg, not the missing key. Normalize before parsing, same idiom as
    affected.py/serve.py.

    Accepts a path (size-cap-checked via the security module, then parsed)
    or an already-parsed dict (no size check — the caller owns any cap).
    """
    from networkx.readwrite import json_graph
    data = path_or_data
    if not isinstance(data, dict):
        p = Path(data)
        from graphify.security import check_graph_file_size_cap  # lazy: security imports paths
        check_graph_file_size_cap(p)
        data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "links" not in data and "edges" in data:
        data = dict(data, links=data["edges"])
    try:
        return json_graph.node_link_graph(data, edges="links")
    except TypeError:  # networkx too old for the edges kwarg; default is "links"
        return json_graph.node_link_graph(data)


def __getattr__(name: str) -> object:
    if name == "GRAPHIFY_OUT":
        return graphify_out_rel()
    if name == "GRAPHIFY_OUT_NAME":
        return graphify_out_name()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
