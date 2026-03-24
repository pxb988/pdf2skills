"""Unified configuration management for pdf2skills pipeline.

Supports multiple LLM providers and layered .env loading with 4-level priority:
  CLI env vars > system env > <cwd>/.pdf2skills/.env > ~/.pdf2skills/.env
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


# ── Provider defaults ────────────────────────────────────────────────

_PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {
    # provider: (default_model, default_base_url)
    "openai": ("gpt-4o", "https://api.openai.com/v1"),
    "anthropic": ("claude-sonnet-4-20250514", "https://api.anthropic.com"),
    "google": ("gemini-2.0-flash", "https://generativelanguage.googleapis.com/v1beta"),
    "deepseek": ("deepseek-chat", "https://api.deepseek.com/v1"),
    "zhipu": ("glm-4-plus", "https://open.bigmodel.cn/api/paas/v4"),
    "qwen": ("qwen-plus", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "siliconflow": ("deepseek-ai/DeepSeek-V3", "https://api.siliconflow.cn/v1"),
    "custom": ("", ""),
}

PROVIDER_NAMES = tuple(_PROVIDER_DEFAULTS.keys())


# ── Dataclasses ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class LLMProviderConfig:
    """Configuration for a single LLM provider."""

    api_key: str | None = None
    model: str = ""
    base_url: str = ""


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider registry.

    ``active_provider`` selects which provider to use at runtime.
    Valid values: openai | anthropic | google | deepseek | zhipu | qwen | siliconflow | custom | ""
    """

    active_provider: str = ""
    openai: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    anthropic: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    google: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    deepseek: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    zhipu: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    qwen: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    siliconflow: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    custom: LLMProviderConfig = field(default_factory=LLMProviderConfig)

    def get_provider(self, name: str) -> LLMProviderConfig:
        """Return the config for the named provider."""
        if name not in PROVIDER_NAMES:
            raise ValueError(f"Unknown LLM provider: {name!r}. Must be one of {PROVIDER_NAMES}")
        return getattr(self, name)


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable pipeline configuration."""

    # Chunking
    chunk_max_tokens: int = 30_000
    chunk_max_iterations: int = 3
    chunk_anchor_length: int = 30

    # Density analysis
    density_calibration_samples: int = 15

    # Knowledge fusion
    bucket_threshold: float = 0.5

    # Output
    output_language: str = "English"
    max_skill_lines: int = 500
    max_skus_per_batch: int = 15

    # PDF parsing — "auto" | "claude" | "mineru" | "llm" | "pypdf2"
    pdf_parser: str = "auto"

    # MinerU (optional)
    mineru_api_key: str | None = None
    mineru_base_url: str = "https://mineru.net/api/v4/extract/task"

    # LLM providers
    llm: LLMConfig = field(default_factory=LLMConfig)

    def get_active_llm(self) -> LLMProviderConfig | None:
        """Return the currently active LLM provider config, or None."""
        name = self.llm.active_provider
        if not name:
            return None
        provider = self.llm.get_provider(name)
        if not provider.api_key:
            return None
        return provider

    def resolve_pdf_parser(self) -> str:
        """Resolve ``pdf_parser="auto"`` to a concrete parser name.

        Priority: mineru (if key set) > llm (if provider active) > claude.
        Non-auto values are returned as-is.
        """
        if self.pdf_parser != "auto":
            return self.pdf_parser

        if self.mineru_api_key:
            return "mineru"
        if self.get_active_llm() is not None:
            return "llm"
        return "claude"


# ── Env resolution ───────────────────────────────────────────────────

def _resolve_env(env_path: Path | None = None) -> dict[str, str | None]:
    """Build a merged env dict with 4-level priority (highest wins):

    1. ``os.environ`` (CLI / system env vars)
    2. ``<cwd>/.pdf2skills/.env`` (project-level)
    3. ``~/.pdf2skills/.env`` (user-level)

    If ``env_path`` is given it is loaded at project-level priority
    (for backward compatibility with the old ``load_config(env_path=)`` API).
    """
    merged: dict[str, str | None] = {}

    # Layer 1 (lowest): user-level
    user_env = Path.home() / ".pdf2skills" / ".env"
    if user_env.is_file():
        merged.update(dotenv_values(user_env))

    # Layer 2: project-level
    project_env = Path.cwd() / ".pdf2skills" / ".env"
    if project_env.is_file():
        merged.update(dotenv_values(project_env))

    # Backward-compat: explicit env_path overrides project-level
    if env_path and env_path.is_file():
        merged.update(dotenv_values(env_path))

    # Layer 3 (highest): real environment variables — only override keys
    # that are actually set in os.environ (to preserve .env defaults for
    # keys the user hasn't explicitly exported).
    for key in list(merged.keys()):
        if key in os.environ:
            merged[key] = os.environ[key]

    return merged


def _build_provider(env: dict[str, str | None], provider: str) -> LLMProviderConfig:
    """Construct an ``LLMProviderConfig`` from env vars for *provider*."""
    prefix = provider.upper()
    default_model, default_url = _PROVIDER_DEFAULTS[provider]

    def _val(key: str) -> str | None:
        return os.environ.get(key) or env.get(key) or None

    return LLMProviderConfig(
        api_key=_val(f"{prefix}_API_KEY"),
        model=_val(f"{prefix}_MODEL") or default_model,
        base_url=_val(f"{prefix}_BASE_URL") or default_url,
    )


def load_config(env_path: Path | None = None) -> PipelineConfig:
    """Load configuration from layered .env files + environment variables."""
    env = _resolve_env(env_path)

    def _get(key: str, default: str = "") -> str:
        val = os.environ.get(key) or env.get(key)
        return val if val else default

    def _int(key: str, default: int) -> int:
        val = _get(key)
        return int(val) if val else default

    def _float(key: str, default: float) -> float:
        val = _get(key)
        return float(val) if val else default

    # Build per-provider configs
    providers = {name: _build_provider(env, name) for name in PROVIDER_NAMES}

    llm_config = LLMConfig(
        active_provider=_get("LLM_PROVIDER"),
        **providers,
    )

    return PipelineConfig(
        chunk_max_tokens=_int("CHUNK_MAX_TOKENS", 30_000),
        chunk_max_iterations=_int("CHUNK_MAX_ITERATIONS", 3),
        chunk_anchor_length=_int("CHUNK_ANCHOR_LENGTH", 30),
        density_calibration_samples=_int("DENSITY_CALIBRATION_SAMPLES", 15),
        bucket_threshold=_float("BUCKET_THRESHOLD", 0.5),
        output_language=_get("OUTPUT_LANGUAGE", "English"),
        max_skill_lines=_int("MAX_SKILL_LINES", 500),
        max_skus_per_batch=_int("MAX_SKUS_PER_BATCH", 15),
        pdf_parser=_get("PDF_PARSER", "auto"),
        mineru_api_key=_get("MINERU_API_KEY") or None,
        mineru_base_url=_get("MINERU_BASE_URL", "https://mineru.net/api/v4/extract/task"),
        llm=llm_config,
    )
