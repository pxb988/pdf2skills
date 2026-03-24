"""Tests for pipeline state and config management."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from src.pipeline.config import (
    LLMConfig,
    LLMProviderConfig,
    PipelineConfig,
    PROVIDER_NAMES,
    _resolve_env,
    load_config,
)
from src.pipeline.state import PipelineState, STAGES


class TestLLMProviderConfig:
    def test_defaults(self):
        cfg = LLMProviderConfig()
        assert cfg.api_key is None
        assert cfg.model == ""
        assert cfg.base_url == ""

    def test_frozen(self):
        cfg = LLMProviderConfig(api_key="k")
        with pytest.raises(AttributeError):
            cfg.api_key = "other"


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.active_provider == ""
        assert cfg.openai == LLMProviderConfig()

    def test_get_provider(self):
        provider = LLMProviderConfig(api_key="sk-test", model="gpt-4o")
        cfg = LLMConfig(active_provider="openai", openai=provider)
        assert cfg.get_provider("openai") is provider

    def test_get_provider_invalid(self):
        cfg = LLMConfig()
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            cfg.get_provider("invalid_name")

    def test_all_providers_accessible(self):
        cfg = LLMConfig()
        for name in PROVIDER_NAMES:
            assert isinstance(cfg.get_provider(name), LLMProviderConfig)


class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig()
        assert config.chunk_max_tokens == 30_000
        assert config.output_language == "English"
        assert config.pdf_parser == "auto"
        assert config.bucket_threshold == 0.5
        assert isinstance(config.llm, LLMConfig)

    def test_immutable(self):
        config = PipelineConfig()
        with pytest.raises(AttributeError):
            config.chunk_max_tokens = 999

    def test_get_active_llm_none(self):
        config = PipelineConfig()
        assert config.get_active_llm() is None

    def test_get_active_llm_no_key(self):
        config = PipelineConfig(
            llm=LLMConfig(active_provider="openai")
        )
        assert config.get_active_llm() is None

    def test_get_active_llm_with_key(self):
        provider = LLMProviderConfig(api_key="sk-test", model="gpt-4o", base_url="https://api.openai.com/v1")
        config = PipelineConfig(
            llm=LLMConfig(active_provider="openai", openai=provider)
        )
        active = config.get_active_llm()
        assert active is not None
        assert active.api_key == "sk-test"
        assert active.model == "gpt-4o"

    def test_resolve_pdf_parser_non_auto(self):
        config = PipelineConfig(pdf_parser="mineru")
        assert config.resolve_pdf_parser() == "mineru"

    def test_resolve_pdf_parser_auto_fallback_claude(self):
        config = PipelineConfig(pdf_parser="auto")
        assert config.resolve_pdf_parser() == "claude"

    def test_resolve_pdf_parser_auto_mineru(self):
        config = PipelineConfig(pdf_parser="auto", mineru_api_key="key123")
        assert config.resolve_pdf_parser() == "mineru"

    def test_resolve_pdf_parser_auto_llm(self):
        provider = LLMProviderConfig(api_key="sk-test", model="m", base_url="http://x")
        config = PipelineConfig(
            pdf_parser="auto",
            llm=LLMConfig(active_provider="deepseek", deepseek=provider),
        )
        assert config.resolve_pdf_parser() == "llm"

    def test_resolve_pdf_parser_auto_mineru_over_llm(self):
        """MinerU takes priority over LLM when both are configured."""
        provider = LLMProviderConfig(api_key="sk-test", model="m", base_url="http://x")
        config = PipelineConfig(
            pdf_parser="auto",
            mineru_api_key="mineru-key",
            llm=LLMConfig(active_provider="openai", openai=provider),
        )
        assert config.resolve_pdf_parser() == "mineru"


class TestResolveEnv:
    def test_empty_when_no_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env = _resolve_env()
        assert isinstance(env, dict)

    def test_project_env_loading(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env_dir = tmp_path / ".pdf2skills"
        env_dir.mkdir()
        (env_dir / ".env").write_text("LLM_PROVIDER=deepseek\n")
        env = _resolve_env()
        assert env.get("LLM_PROVIDER") == "deepseek"

    def test_os_environ_overrides_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env_dir = tmp_path / ".pdf2skills"
        env_dir.mkdir()
        (env_dir / ".env").write_text("LLM_PROVIDER=deepseek\n")
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        env = _resolve_env()
        assert env.get("LLM_PROVIDER") == "openai"

    def test_explicit_env_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env_file = tmp_path / "custom.env"
        env_file.write_text("BUCKET_THRESHOLD=0.8\n")
        env = _resolve_env(env_path=env_file)
        assert env.get("BUCKET_THRESHOLD") == "0.8"


class TestLoadConfig:
    def test_defaults(self):
        config = load_config()
        assert isinstance(config, PipelineConfig)
        assert config.chunk_max_tokens == 30_000

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CHUNK_MAX_TOKENS", "10000")
        monkeypatch.setenv("PDF_PARSER", "llm")
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        config = load_config()
        assert config.chunk_max_tokens == 10000
        assert config.pdf_parser == "llm"
        assert config.llm.active_provider == "deepseek"
        assert config.llm.deepseek.api_key == "sk-test"

    def test_provider_defaults(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-abc")
        config = load_config()
        assert config.llm.openai.api_key == "sk-abc"
        assert config.llm.openai.model == "gpt-4o"
        assert config.llm.openai.base_url == "https://api.openai.com/v1"

    def test_provider_model_override(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds")
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-coder")
        config = load_config()
        assert config.llm.deepseek.model == "deepseek-coder"

    def test_custom_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "custom")
        monkeypatch.setenv("CUSTOM_API_KEY", "sk-custom")
        monkeypatch.setenv("CUSTOM_MODEL", "my-model")
        monkeypatch.setenv("CUSTOM_BASE_URL", "https://my-llm.example.com/v1")
        config = load_config()
        active = config.get_active_llm()
        assert active is not None
        assert active.model == "my-model"
        assert active.base_url == "https://my-llm.example.com/v1"

    def test_backward_compat_env_path(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("OUTPUT_LANGUAGE=Chinese\n")
        config = load_config(env_path=env_file)
        assert config.output_language == "Chinese"


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
