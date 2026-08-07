"""Plugin ``skills/`` copies must stay in sync with canonical ``.agents/skills/``.

Codex reads ``.agents/skills/`` (agentskills.io spec); the Claude Code plugin
reads ``skills/``. The canonical copy is ``.agents/skills/`` — on failure,
copy the canonical file over the plugin copy.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DISTRIBUTED_SKILLS = ["psim-circuit-workflow", "psim-circuit-optimization"]


@pytest.mark.parametrize("name", DISTRIBUTED_SKILLS)
def test_plugin_skill_matches_canonical(name: str):
    canonical = (REPO / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    plugin_copy = (REPO / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    assert canonical == plugin_copy, (
        f"skills/{name}/SKILL.md drifted from .agents/skills/{name}/SKILL.md — "
        "copy the canonical file over the plugin copy"
    )
