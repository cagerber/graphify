"""Scope of the skill-version staleness check (fork side).

Upstream compares the running package version against every platform skill
destination. In a project-scoped setup (``GRAPHIFY_OUT`` set — the consumer owns
``.agents/skills/graphify`` and the global IDE copies are unrelated) only that
project copy is meaningful, so a stale global skill must not warn on every
``update``/``hook-check``.
"""

from __future__ import annotations

import os
from pathlib import Path


def skill_version_check_targets() -> set[Path]:
    """Skill install paths to compare against the running package version."""
    if not os.environ.get("GRAPHIFY_OUT", "").strip():
        # Imported lazily: these live in the CLI entry module, which calls us.
        from graphify.__main__ import _PLATFORM_CONFIG, _platform_skill_destination

        return {_platform_skill_destination(name) for name in _PLATFORM_CONFIG}

    project_skill = Path(".agents/skills/graphify/SKILL.md")
    stamp = project_skill.parent / ".graphify_version"
    try:
        if stamp.exists():
            return {project_skill}
    except OSError:
        return set()
    return set()
