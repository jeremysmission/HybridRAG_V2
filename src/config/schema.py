"""
HybridRAG V2 configuration schema.

Single config, no modes. Validated once at boot, immutable after.
Two hardware presets (beast, laptop) — selected in config.yaml.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class PathsConfig(BaseModel):
    """File system paths for V2 stores and data."""

    lance_db: str = Field(
        default="data/index/lancedb",
        description="LanceDB directory for vector + BM25 hybrid store.",
    )
    entity_db: str = Field(
        default="data/index/entities.sqlite3",
        description="SQLite database for validated entities and relationships.",
    )
    embedengine_output: str = Field(
        default="data/source",
        description="Where CorpusForge drops nightly export packages.",
    )
    site_vocabulary: str = Field(
        default="config/site_vocabulary.yaml",
        description="Controlled vocabulary YAML for IGS site normalization.",
    )


class RetrievalConfig(BaseModel):
    """Retrieval and reranking parameters."""

    top_k: int = Field(default=10, ge=1, description="Chunks returned to LLM after reranking.")
    candidate_pool: int = Field(default=30, ge=1, description="Chunks retrieved before reranking.")
    min_score: float = Field(default=0.1, ge=0.0, le=1.0, description="Minimum retrieval score threshold.")
    reranker_enabled: bool = Field(default=True, description="Enable FlashRank reranking.")
    reranker_top_n: int = Field(default=30, ge=1, description="Candidates sent to reranker.")

    @model_validator(mode="after")
    def pool_gte_top_k(self) -> "RetrievalConfig":
        if self.candidate_pool < self.top_k:
            raise ValueError(
                f"candidate_pool ({self.candidate_pool}) must be >= top_k ({self.top_k})"
            )
        return self


class LLMConfig(BaseModel):
    """LLM settings — supports Azure OpenAI, Commercial OpenAI, and Ollama."""

    model: str = Field(default="gpt-4o", description="Primary LLM model name.")
    deployment: str = Field(default="gpt-4o", description="Azure deployment name (Azure only).")
    context_window: int = Field(default=128000, ge=1, description="Model context window in tokens.")
    max_tokens: int = Field(default=16384, ge=1, description="Max output tokens per response.")
    temperature: float = Field(default=0.08, ge=0.0, le=2.0, description="Generation temperature.")
    timeout_seconds: int = Field(default=180, ge=10, description="API call timeout.")
    api_base: str = Field(default="", description="Endpoint URL. Leave empty for commercial OpenAI (auto).")
    api_version: str = Field(default="2024-10-21", description="Azure OpenAI API version.")
    provider: str = Field(default="auto", description="'auto', 'azure', 'openai', or 'ollama'.")


class ExtractionConfig(BaseModel):
    """Quality-gated entity extraction settings."""

    min_confidence: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Minimum confidence to accept an extracted entity.",
    )
    model: str = Field(
        default="phi4:14b-q4_K_M",
        description="Model for bulk entity extraction. Default: phi4 local ($0). Alt: gpt-4o-mini (API, fast).",
    )
    part_patterns: list[str] = Field(
        default=[
            r"ARC-\d{4}",
            r"IGSI-\d+",
            r"PO-\d{4}-\d{4}",
            r"SN \d+",
            r"SEMS3D-\d+",
        ],
        description="Regex patterns for valid part numbers.",
    )
    gliner_enabled: bool = Field(default=False, description="Use GLiNER2 for first-pass NER (waiver pending).")
    gpt4o_extraction: bool = Field(default=True, description="Use LLM for semantic extraction.")


class ServerConfig(BaseModel):
    """FastAPI server settings."""

    host: str = Field(default="127.0.0.1", description="Bind address.")
    port: int = Field(default=8000, ge=1, le=65535, description="Bind port.")


class CRAGConfig(BaseModel):
    """Corrective RAG verification loop (Sprint 3+)."""

    enabled: bool = Field(default=False, description="Enable CRAG verification loop.")
    confidence_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0,
        description="Below this confidence, trigger re-retrieval.",
    )
    max_retries: int = Field(default=2, ge=0, le=5, description="Max CRAG retry attempts.")
    verifier_model: str = Field(default="gpt-oss-20b", description="Model for CRAG grading.")


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

class V2Config(BaseModel):
    """
    HybridRAG V2 top-level configuration.

    Single config, no modes. hardware_preset selects beast or laptop defaults.
    """

    model_config = {"extra": "forbid"}

    paths: PathsConfig = Field(default_factory=PathsConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    crag: CRAGConfig = Field(default_factory=CRAGConfig)
    hardware_preset: str = Field(default="beast", description="'beast' or 'laptop'.")

    @field_validator("hardware_preset")
    @classmethod
    def validate_preset(cls, v: str) -> str:
        allowed = {"beast", "laptop"}
        if v not in allowed:
            raise ValueError(f"hardware_preset must be one of {allowed}, got '{v}'")
        return v


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path = "config/config.yaml") -> V2Config:
    """
    Load and validate HybridRAG V2 configuration from YAML.

    Falls back to Pydantic defaults for any missing fields.
    """
    path = Path(config_path)
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            raw = yaml.safe_load(f) or {}
    else:
        print(f"[WARN] Config file not found at {path}, using defaults.", file=sys.stderr)
        raw = {}

    return V2Config(**raw)
