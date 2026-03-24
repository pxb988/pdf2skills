"""Tests for pipeline state and config management."""

import json
import pytest
from pathlib import Path

from src.pipeline.config import PipelineConfig, load_config
from src.pipeline.state import PipelineState, STAGES


class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig()
        assert config.chunk_max_tokens == 30_000
        assert config.output_language == "English"
        assert config.pdf_parser == "claude"
        assert config.bucket_threshold == 0.5

    def test_immutable(self):
        config = PipelineConfig()
        with pytest.raises(AttributeError):
            config.chunk_max_tokens = 999

    def test_load_config_defaults(self):
        config = load_config()
        assert isinstance(config, PipelineConfig)
        assert config.chunk_max_tokens == 30_000


class TestPipelineState:
    def test_new_state(self, tmp_path: Path):
        state = PipelineState(output_dir=tmp_path)
        assert state.completed_stages == []
        assert state.next_stage() == "pdf_parse"

    def test_mark_complete(self, tmp_path: Path):
        state = PipelineState(output_dir=tmp_path)
        state.mark_complete("pdf_parse", {"chars": 5000})
        assert state.is_complete("pdf_parse")
        assert not state.is_complete("chunking")
        assert state.next_stage() == "chunking"
        assert state.stage_metadata["pdf_parse"]["chars"] == 5000

    def test_persistence(self, tmp_path: Path):
        state = PipelineState(output_dir=tmp_path)
        state.mark_complete("pdf_parse")
        state.mark_complete("chunking")

        loaded = PipelineState.load(tmp_path)
        assert loaded.is_complete("pdf_parse")
        assert loaded.is_complete("chunking")
        assert loaded.next_stage() == "density"

    def test_all_stages_complete(self, tmp_path: Path):
        state = PipelineState(output_dir=tmp_path)
        for stage in STAGES:
            state.mark_complete(stage)
        assert state.next_stage() is None

    def test_artifact_paths(self, tmp_path: Path):
        state = PipelineState(output_dir=tmp_path)
        assert state.markdown_path == tmp_path / "full.md"
        assert state.chunks_dir == tmp_path / "chunks"
        assert state.skills_dir == tmp_path / "generated_skills"

    def test_load_nonexistent(self, tmp_path: Path):
        state = PipelineState.load(tmp_path / "nonexistent")
        assert state.completed_stages == []

    def test_idempotent_mark(self, tmp_path: Path):
        state = PipelineState(output_dir=tmp_path)
        state.mark_complete("pdf_parse")
        state.mark_complete("pdf_parse")
        assert state.completed_stages.count("pdf_parse") == 1
