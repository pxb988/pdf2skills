"""Unified configuration management for pdf2skills pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


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

    # PDF parsing
    pdf_parser: str = "claude"  # "claude" | "mineru" | "pypdf2"

    # MinerU (optional)
    mineru_api_key: str | None = None
    mineru_base_url: str = "https://mineru.net/api/v4/extract/task"


def load_config(env_path: Path | None = None) -> PipelineConfig:
    """Load configuration from environment variables.

    Falls back to defaults for all values. Only needed when
    overriding defaults via .env file.
    """
    if env_path and env_path.exists():
        load_dotenv(env_path)

    def _int(key: str, default: int) -> int:
        val = os.getenv(key)
        return int(val) if val else default

    def _float(key: str, default: float) -> float:
        val = os.getenv(key)
        return float(val) if val else default

    def _str(key: str, default: str) -> str:
        return os.getenv(key, default)

    return PipelineConfig(
        chunk_max_tokens=_int("CHUNK_MAX_TOKENS", 30_000),
        chunk_max_iterations=_int("CHUNK_MAX_ITERATIONS", 3),
        chunk_anchor_length=_int("CHUNK_ANCHOR_LENGTH", 30),
        density_calibration_samples=_int("DENSITY_CALIBRATION_SAMPLES", 15),
        bucket_threshold=_float("BUCKET_THRESHOLD", 0.5),
        output_language=_str("OUTPUT_LANGUAGE", "English"),
        max_skill_lines=_int("MAX_SKILL_LINES", 500),
        max_skus_per_batch=_int("MAX_SKUS_PER_BATCH", 15),
        pdf_parser=_str("PDF_PARSER", "claude"),
        mineru_api_key=os.getenv("MINERU_API_KEY"),
        mineru_base_url=_str("MINERU_BASE_URL", "https://mineru.net/api/v4/extract/task"),
    )
