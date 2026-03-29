"""Format generated skills into Claude Code Skill directory structure."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GeneratedSkill:
    """A single generated skill ready for packaging."""

    skill_name: str
    source_sku_uuids: list[str]
    skill_md: str
    references: dict[str, str] = field(default_factory=dict)


def package_skills(skills: list[GeneratedSkill], output_dir: Path) -> Path:
    """Write skills to the output directory in Claude Code Skill format.

    Structure:
        output_dir/
        ├── index.md
        ├── generation_metadata.json
        ├── skill-name-1/
        │   ├── SKILL.md
        │   └── references/
        │       └── details.md
        └── ...
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for skill in skills:
        skill_dir = output_dir / skill.skill_name
        skill_dir.mkdir(exist_ok=True)

        (skill_dir / "SKILL.md").write_text(skill.skill_md, encoding="utf-8")

        if skill.references:
            refs_dir = skill_dir / "references"
            refs_dir.mkdir(exist_ok=True)
            for filename, content in skill.references.items():
                (refs_dir / filename).write_text(content, encoding="utf-8")

    # Write generation metadata
    metadata = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_skills": len(skills),
        "skills": [
            {
                "name": s.skill_name,
                "source_sku_uuids": s.source_sku_uuids,
                "has_references": bool(s.references),
            }
            for s in skills
        ],
    }
    (output_dir / "generation_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return output_dir


def generate_fallback_index(skills: list[GeneratedSkill]) -> str:
    """Generate a simple index.md when LLM generation fails."""
    lines = [
        "# Generated Skills",
        "",
        "Skills generated from book content.",
        "",
        "## Available Skills",
        "",
    ]
    for skill in skills:
        lines.append(f"- [{skill.skill_name}]({skill.skill_name}/SKILL.md)")
    return "\n".join(lines)
