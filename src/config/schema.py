"""
HybridRAG V2 configuration schema.

Single config, no modes. Validated once at boot, immutable after.
Two hardware presets (primary workstation, laptop) — selected in config.yaml.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
        description="Controlled vocabulary YAML for enterprise program site normalization.",
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
            r"SN[-: ]?\d+",
            r"SEMS3D-\d+",
            r"[A-Z]{2,}-\d{3,4}",
            r"WR-\d{4}",
            r"FM-\d{3}",
            r"AB-\d{3}",
            r"PS-\d{3}",
            r"AH-\d{3}",
        ],
        description="Regex patterns for valid part numbers.",
    )
    security_standard_exclude_patterns: list[str] = Field(
        default=[
            # security standard SP 800-53 Rev 5 control families (all 20). Suffix must
            # be 1-2 digits + optional enhancement — the Rev 5 catalog
            # tops out at SC-51, so any 3+ digit suffix is NOT a security standard
            # control. The digit-length discriminator is what keeps real
            # hardware parts like PS-800 (Granite Peak backordered item)
            # and SA-9000 (spectrum analyzer) passing through even
            # though PS and SA are both security standard family prefixes.
            r"^(?:AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)-\d{1,2}(\(\d+\))?$",
            # STIG baseline platform codes — 3-5 digit suffix. AS/OS/
            # GPOS/HS are STIG-only prefixes with no real-part
            # collisions in this corpus.
            r"^(?:AS|OS|GPOS|HS)-\d{3,5}$",
            # STIG / DISA Control Correlation Identifier
            r"^CCI-\d+$",
            # STIG / DISA Vulnerability ID
            r"^SV-\d+$",
            # security standard SP 800 publication reference
            r"^SP[\s\-]?800\b",
            # MITRE Common Vulnerabilities and Exposures. Some OCR /
            # chunking splits turn CVE-2024-7525 into a shorter CVE-202
            # fragment, so reject the governed namespace broadly.
            r"^CVE-\d{3,}(?:-\d+)*$",
            # MITRE Common Configuration Enumeration
            r"^CCE-\d+$",
            # Red Hat Security Advisories from scan/plugin findings
            r"^RHSA-\d{4}$",
            # Security tooling shorthand and generic cyber debris seen in
            # the live corpus audit. These are not physical parts.
            r"^SNMP$",
            r"^APP-\d+$",
            r"^SERVICE_(?:START|STOP)$",
            r"^[A-Z0-9]+(?:_[A-Z0-9]+)+$",
            r"^CNSSI-\d+$",
            r"^DD-\d{4}$",
            r"^DO-\d{4}$",
            r"^enterprise program(?:I|CC)?-\d{3,5}$",
            r"^MSR-\d+$",
            r"^DV-\d{2,4}$",
            r"^IEEE-\d+$",
            r"^SNOW$",
        ],
        description=(
            "Regex patterns matched against the UPPER()-case candidate "
            "at every PART / PO emit site in RegexPreExtractor and "
            "EventBlockParser. Any match rejects the candidate as a "
            "security-standard identifier, not a physical part or "
            "procurement ID. Default covers security standard SP 800-53 Rev 5 (all "
            "20 families, 1-2 digit suffix discriminator so PS-800 and "
            "SA-9000 hardware survive) + STIG baseline platform codes + "
            "STIG CCI/SV + security standard SP 800 publication refs + MITRE CVE/CCE + "
            "RHSA/security-tooling debris families surfaced by the Tier 1 corpus audit. "
            "Operators running V2 against a different corpus can "
            "override this list per-corpus without changing the "
            "extractor code. Empty list = no exclusion (useful for "
            "cybersecurity doc corpora where the security standard/STIG identifiers "
            "ARE the content). See "
            "docs/NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md "
            "for the rationale, before/after evidence, and Round 2 QA "
            "regression that drove the shift from prefix matching to "
            "regex matching."
        ),
    )
    gliner_enabled: bool = Field(default=False, description="Use GLiNER2 for first-pass NER (waiver pending).")
    gliner_device: str = Field(default="cuda:1", description="Device for GLiNER model. Use cuda:1 on primary workstation.")
    gliner_model: str = Field(default="urchade/gliner_medium-v2.1", description="GLiNER model name.")
    gliner_min_chunk_len: int = Field(default=50, description="Skip chunks shorter than this for GLiNER.")
    gpt4o_extraction: bool = Field(default=True, description="Use LLM for semantic extraction.")
    max_concurrent: int = Field(default=16, ge=1, le=64, description="Max concurrent extraction threads.")


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

    Single config, no modes. hardware_preset selects primary workstation or laptop defaults.
    """

    model_config = {"extra": "forbid"}

    paths: PathsConfig = Field(default_factory=PathsConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    crag: CRAGConfig = Field(default_factory=CRAGConfig)
    hardware_preset: str = Field(default="primary workstation", description="'primary workstation' or 'laptop'.")

    @field_validator("hardware_preset")
    @classmethod
    def validate_preset(cls, v: str) -> str:
        allowed = {"primary workstation", "laptop"}
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
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            raw = yaml.safe_load(f) or {}
    else:
        print(f"[WARN] Config file not found at {path}, using defaults.", file=sys.stderr)
        raw = {}

    cfg = V2Config(**raw)

    for field_name in ("lance_db", "entity_db", "embedengine_output", "site_vocabulary"):
        value = getattr(cfg.paths, field_name)
        resolved = Path(value)
        if not resolved.is_absolute():
            resolved = PROJECT_ROOT / resolved
        setattr(cfg.paths, field_name, str(resolved))

    return cfg
