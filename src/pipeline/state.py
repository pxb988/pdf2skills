"""Pipeline state and checkpoint management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


STAGES = (
    "pdf_parse",
    "chunking",
    "density",
    "sku_extract",
    "fusion",
    "skill_gen",
    "router",
    "glossary",
)


@dataclass
class PipelineState:
    """Tracks which pipeline stages have completed."""

    output_dir: Path
    completed_stages: list[str] = field(default_factory=list)
    stage_metadata: dict[str, Any] = field(default_factory=dict)

    # --- persistence --------------------------------------------------

    @property
    def _state_file(self) -> Path:
        return self.output_dir / ".pipeline_state.json"

    def save(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "completed_stages": self.completed_stages,
            "stage_metadata": self.stage_metadata,
        }
        self._state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, output_dir: Path) -> PipelineState:
        state_file = output_dir / ".pipeline_state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return cls(
                output_dir=output_dir,
                completed_stages=data.get("completed_stages", []),
                stage_metadata=data.get("stage_metadata", {}),
            )
        return cls(output_dir=output_dir)

    # --- helpers ------------------------------------------------------

    def is_complete(self, stage: str) -> bool:
        return stage in self.completed_stages

    def mark_complete(self, stage: str, metadata: dict[str, Any] | None = None) -> None:
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)
        if metadata:
            self.stage_metadata[stage] = metadata
        self.save()

    def next_stage(self) -> str | None:
        for stage in STAGES:
            if stage not in self.completed_stages:
                return stage
        return None

    # --- artifact paths -----------------------------------------------

    @property
    def markdown_path(self) -> Path:
        return self.output_dir / "full.md"

    @property
    def chunks_dir(self) -> Path:
        return self.output_dir / "chunks"

    @property
    def chunks_index(self) -> Path:
        return self.chunks_dir / "chunks_index.json"

    @property
    def density_path(self) -> Path:
        return self.output_dir / "density_scores.json"

    @property
    def skus_dir(self) -> Path:
        return self.output_dir / "skus"

    @property
    def skus_index(self) -> Path:
        return self.skus_dir / "skus_index.json"

    @property
    def buckets_path(self) -> Path:
        return self.skus_dir / "buckets.json"

    @property
    def skills_dir(self) -> Path:
        return self.output_dir / "generated_skills"

    @property
    def router_path(self) -> Path:
        return self.skills_dir / "router.json"

    @property
    def glossary_path(self) -> Path:
        return self.output_dir / "glossary.json"
