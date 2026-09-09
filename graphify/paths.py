"""Canonical graphify output paths (GRAPHIFY_OUT env).

All runtime resolution goes through here so import-time defaults do not
freeze ``graphify-out/`` when the env var is set later (e.g. consumer
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
from pathlib import Path, PurePosixPath, PureWindowsPath

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
    fd, tmp = tempfile.mkstemp(dir=str(real.parent), prefix=".gfy-", suffix=".tmp")
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
            # The temp was chmod'd to match the destination above, so when the
            # destination is read-only the temp is too — and Windows refuses to
            # unlink a read-only file. Clear the bit and retry, or every failed
            # write leaks a `.gfy-*.tmp` into the output directory.
            try:
                os.chmod(tmp, stat.S_IWRITE)
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
    """Relative or absolute output directory from GRAPHIFY_OUT (default graphify-out).

    Precedence: the environment, then an explicitly-assigned module attribute
    (tests/embedding hosts that ``setattr``), then the default. Reading the env
    first matters: ``monkeypatch.setattr`` restores the PEP 562 value as a real
    module attribute on teardown, which would otherwise shadow the env for the
    rest of the process.
    """
    from_env = os.environ.get("GRAPHIFY_OUT")
    if from_env:
        return from_env
    explicit = globals().get("GRAPHIFY_OUT")
    if isinstance(explicit, str) and explicit:
        return explicit
    return _DEFAULT_REL


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
    """Repository root for resolving relative ``GRAPHIFY_OUT`` during subpath scans.

    Relative watch paths that resolve *inside* the current directory anchor at
    cwd (the fork's project-root ``GRAPHIFY_OUT`` — a subdir watch shares the
    project graph). A relative target that escapes cwd (e.g. ``../other``,
    watching an external project) is its own root: its manifest and graph must
    live next to the target, not in the caller's output dir (#2316).
    """
    if watch_path is None:
        return Path.cwd().resolve()
    wp = Path(watch_path)
    if wp.is_absolute():
        return wp.resolve()
    resolved = wp.resolve()
    cwd = Path.cwd().resolve()
    if cwd == resolved or cwd in resolved.parents:
        return cwd
    return resolved


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
    """Directory basename(s) to skip when scanning source (configured-out top level only).

    Only the *top-level* output dir name is a global skip (e.g. ``graphify-out`` for
    ``graphify-out/nlp``): deeper parts of the configured output path are pruned by
    full-path equality in ``detect`` (#2273) and must not name-prune same-named
    source dirs. Absolute configured outputs contribute no scan-root name.
    """
    names = {_DEFAULT_REL}
    rel = graphify_out_rel()
    rel_path = Path(rel)
    if not rel_path.is_absolute() and rel not in (".", ""):
        names.add(rel_path.parts[0])
    return frozenset(names)


def is_absolute_any_platform(p: "str | Path | None") -> bool:
    """Whether *p* is absolute under POSIX **or** Windows rules.

    ``Path.is_absolute()`` and ``os.path.isabs()`` answer for the HOST os only,
    which is the wrong question for a path that was *stored* — a ``source_file``
    in ``graph.json``, a ``prune_sources`` entry, a cache key. Those travel
    between machines (build in Docker/CI, update on a Windows workstation, or
    the reverse), so the host's rules do not describe the string in hand:

    - On Windows, ``WindowsPath("/home/ci/repo/docs/a.md").is_absolute()`` is
      False — no drive letter — so a Linux-built graph's absolute paths read as
      relative and get baked into node IDs or joined under the scan root (#2618).
    - On POSIX, ``PosixPath("C:/Users/u/a.md").is_absolute()`` is False for the
      mirror-image reason (#2197, #1789).

    ``os.path.isabs`` is additionally not stable across supported interpreters:
    Python 3.13 changed ``ntpath.isabs`` so a path starting with a single slash
    is no longer absolute, where 3.10–3.12 said it was. The project supports
    >=3.10, so a guard written on it silently means different things per version.

    Answering for both platforms is the conservative choice for stored paths:
    treating a path as absolute at worst declines to relativize it (the string is
    kept as-is), whereas treating an absolute path as relative corrupts identity.
    Covers drive-letter, UNC, and POSIX-root forms with either separator.

    NOTE: this is for STORED/portable paths. Code resolving a path against the
    real local filesystem (``cli``, ``detect``, ``hooks``) must keep using
    ``Path.is_absolute()`` — there the host's rules are exactly right.
    """
    if not p:
        return False
    s = str(p)
    return PurePosixPath(s).is_absolute() or PureWindowsPath(s).is_absolute()


# Legacy Windows path ceiling. Unless long-path support is enabled *and* every
# consumer opts in, the ENTIRE path — drive, directories, filename, and the
# terminating NUL — must fit in MAX_PATH (260) characters, so the usable budget
# is 259. POSIX has no equivalent whole-path ceiling in practice; its limit is
# per-component (NAME_MAX, conventionally 255 bytes).
_WINDOWS_MAX_PATH = 260

# Floor for the stem budget below. A directory deep enough to push the budget
# under this cannot host readable filenames anyway; keep enough room for
# _cap_filename's "_" + 8-char digest so a truncated stem stays collision-safe
# and deterministic rather than degenerating into a bare prefix.
_MIN_STEM_BUDGET = 16


def stem_filename_budget(output_dir: "str | Path", *, reserve: int = 0, limit: int = 200) -> int:
    """Largest filename stem an exporter may write directly into ``output_dir``.

    Exporters cap note/article filenames so they stay under the filesystem's
    per-component limit (conventionally NAME_MAX=255 bytes, hence the 200
    default). That is the right question on POSIX and the wrong one on Windows,
    where the constraint is on the WHOLE path, not the component: a 200-char
    stem under a perfectly ordinary vault directory such as
    ``C:\\Users\\me\\projects\\svc\\graphify-out\\obsidian`` exceeds MAX_PATH and
    the write dies with ``FileNotFoundError``, aborting the export mid-vault.

    Returns ``limit`` unchanged on POSIX, so existing output is byte-for-byte
    stable there. On Windows it returns the smaller of ``limit`` and whatever
    still fits inside MAX_PATH once ``output_dir``, the separator, ``reserve``
    (room for caller-added prefixes/collision suffixes) and the ``.md``
    extension are accounted for.

    The budget is a CHARACTER count, but callers that cap UTF-8 BYTES may pass
    it straight through: a string's UTF-8 length is never below its character
    length, so a byte-capped stem always satisfies the character ceiling too.
    """
    if os.name != "nt":
        return limit
    try:
        base = os.path.abspath(str(output_dir))
    except (OSError, ValueError):
        return limit
    # An extended-length path ("\\?\C:\...", "\\?\UNC\...") opts out of MAX_PATH
    # entirely, so nothing needs shrinking.
    if base.startswith("\\\\?\\"):
        return limit
    budget = (_WINDOWS_MAX_PATH - 1) - len(base) - len(os.sep) - reserve - len(".md")
    return max(_MIN_STEM_BUDGET, min(limit, budget))


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
