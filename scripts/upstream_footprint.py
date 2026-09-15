#!/usr/bin/env python3
"""Measure the fork's footprint on upstream-owned files.

Every line of upstream code this fork deletes is a line that will conflict the
next time upstream touches it. Fork-only files are free; edits inside upstream
files are not. This reports that surface per file, and `--check` fails when a
deleted upstream line is *prose* — a comment or docstring — because rewriting
upstream's prose (or reformatting its code) buys nothing and costs a conflict
every merge. Deliberate deltas should be additive; when a line really must
change, change the fewest lines and say why in a comment.

Usage:
    python scripts/upstream_footprint.py                 # report
    python scripts/upstream_footprint.py --check         # fail on prose deletions
    python scripts/upstream_footprint.py --base upstream/v8 --top 20
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections import Counter

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DEFAULT_BASE = "upstream/v8"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def upstream_default(base: str) -> str:
    if base:
        return base
    try:
        head = git("symbolic-ref", "refs/remotes/upstream/HEAD").strip()
    except subprocess.CalledProcessError:
        return DEFAULT_BASE
    return head


def prose_lines(blob: str) -> set[int]:
    """1-based line numbers of *blob* that are comments or docstrings."""
    lines = blob.splitlines()
    prose = {i + 1 for i, line in enumerate(lines) if line.lstrip().startswith("#")}
    try:
        tree = ast.parse(blob)
    except SyntaxError:  # not Python (shell payloads, lock files, docs)
        return prose
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                first = body[0]
                prose.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return prose


def deleted_upstream_lines(base: str, path: str) -> list[tuple[int, str]]:
    """(upstream line number, text) for every upstream line the worktree drops."""
    diff = git("diff", "-U0", base, "--", path)
    out: list[tuple[int, str]] = []
    lineno = 0
    for line in diff.splitlines():
        m = HUNK.match(line)
        if m:
            lineno = int(m.group(1))
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            out.append((lineno, line[1:]))
            lineno += 1
    return out


def load_allow(path: str = "scripts/upstream_footprint_allow.txt") -> set[str]:
    """Deliberate, justified prose deletions: `path:upstream-line` entries."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return set()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="", help="upstream ref (default: upstream/<HEAD>)")
    ap.add_argument("--check", action="store_true", help="exit 1 on prose deletions")
    ap.add_argument("--top", type=int, default=0, help="only the N worst files")
    args = ap.parse_args()
    base = upstream_default(args.base)
    allowed = load_allow()

    names = git("diff", "--name-status", base).splitlines()
    added = {line.split("\t")[1] for line in names if line.startswith("A\t")}
    modified = [line.split("\t")[1] for line in names if line.startswith("M\t")]

    findings: list[dict] = []
    totals = Counter()
    for path in modified:
        upstream_blob = git("show", f"{base}:{path}") if _in_upstream(base, path) else ""
        prose = prose_lines(upstream_blob) if upstream_blob else set()
        drops = deleted_upstream_lines(base, path)
        prose_drops = [
            (n, t)
            for n, t in drops
            if n in prose and f"{path}:{n}" not in allowed
        ]
        waived = [(n, t) for n, t in drops if n in prose and f"{path}:{n}" in allowed]
        numstat = git("diff", "--numstat", base, "--", path).split("\t")
        findings.append(
            {
                "path": path,
                "added": int(numstat[0]),
                "deleted": int(numstat[1]),
                "prose": prose_drops,
                "waived": waived,
            }
        )
        totals["added"] += int(numstat[0])
        totals["deleted"] += int(numstat[1])
        totals["prose"] += len(prose_drops)
        totals["waived"] += len(waived)

    for path in sorted(added):
        totals["new_files"] += 1
        totals["new_added"] += int(git("diff", "--numstat", base, "--", path).split("\t")[0])

    findings.sort(key=lambda f: (-len(f["prose"]), -f["deleted"]))
    print(f"base: {base}")
    print(
        f"fork-only new files : {totals['new_files']:3} files, +{totals['new_added']} lines (conflict-free)\n"
        f"upstream-owned files: {len(modified):3} modified, +{totals['added']} / -{totals['deleted']}\n"
        f"  of those deletions, {totals['prose']} are upstream prose (comments/docstrings)"
        f" [{totals['waived']} waived]\n"
    )
    shown = findings[: args.top] if args.top else findings
    print(f"{'file':34} {'-lines':>7} {'prose':>6}")
    for f in shown:
        print(f"{f['path']:34} {f['deleted']:7} {len(f['prose']):6}")
    if totals["prose"]:
        print("\nprose deletions (upstream text overwritten for no functional reason):")
        for f in findings:
            for lineno, text in f["prose"][:40]:
                print(f"  {f['path']}:{lineno}: {text.strip()[:96]}")
    if totals["waived"]:
        print("\nwaived prose deletions (scripts/upstream_footprint_allow.txt):")
        for f in findings:
            for lineno, text in f["waived"]:
                print(f"  {f['path']}:{lineno}: {text.strip()[:96]}")
    if args.check and totals["prose"]:
        print("\nFAIL: restore upstream's prose; keep fork deltas additive.")
        return 1
    return 0


def _in_upstream(base: str, path: str) -> bool:
    try:
        git("cat-file", "-e", f"{base}:{path}")
    except subprocess.CalledProcessError:
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
