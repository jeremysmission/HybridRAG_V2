"""Controlled vocabulary pack loader.

Reads sanitized YAML packs from ``config/vocab_packs/`` and exposes them as
typed objects. Packs follow the schema in
``docs/vocab_pack_schema.md`` (mirror of
``HYBRIDRAG_LOCAL_ONLY/VOCABULARY_PACK_SCHEMA_2026-04-15.md``).

Usage::

    from src.vocab import load_all_packs
    packs = load_all_packs("config/vocab_packs")
    for pack in packs:
        print(pack.pack_id, len(pack.entries))

The loader intentionally does NOT promote any entries into extraction
defaults. Promotion is a separate concern and happens elsewhere after
validation against locked-set evidence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


VALID_COLLISION_RISK = {"low", "medium", "high"}
VALID_SOURCE_KIND = {"official_public", "public_secondary", "local_corpus"}
VALID_RELEASE_TIER = {"deployable", "local-only", "mixed"}
VALID_KIND = {"acronym", "form", "location", "alias", "term"}

REQUIRED_PACK_FIELDS = (
    "pack_id",
    "pack_name",
    "domain",
    "version",
    "release_tier",
    "status",
    "entries",
)

REQUIRED_ENTRY_FIELDS = (
    "term_id",
    "canonical",
    "kind",
    "domain",
    "category",
)


class VocabPackError(ValueError):
    """Raised when a pack cannot be parsed or fails validation."""


@dataclass
class VocabEntry:
    """A single controlled-vocabulary entry.

    Core shape matches the required schema fields. Kind-specific extras
    (form_number, common_fields, service, legacy_names, etc.) are kept in
    ``extras`` so the loader does not silently drop them and the caller can
    access them with ``entry.extras.get(...)``.
    """

    term_id: str
    canonical: str
    kind: str
    domain: str
    category: str
    regex_safe: bool
    retrieval_expand: bool
    collision_risk: str
    source_kind: str
    sources: list[dict[str, str]]
    aliases: list[str] = field(default_factory=list)
    expansion: str = ""
    definition_short: str = ""
    confidence: str = ""
    notes: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def alias_set(self) -> set[str]:
        """Case-insensitive alias set, including the canonical form."""
        out = {self.canonical.strip().lower()}
        for alias in self.aliases:
            if alias:
                out.add(alias.strip().lower())
        return out


@dataclass
class VocabPack:
    """A collection of controlled-vocabulary entries with pack-level metadata."""

    pack_id: str
    pack_name: str
    domain: str
    version: str
    release_tier: str
    status: str
    entries: list[VocabEntry]
    description: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    entry_defaults: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""

    def __len__(self) -> int:
        return len(self.entries)

    def by_kind(self, kind: str) -> list[VocabEntry]:
        """Return entries whose ``kind`` matches."""
        return [e for e in self.entries if e.kind == kind]

    def find_by_alias(self, text: str) -> VocabEntry | None:
        """Case-insensitive lookup by canonical or alias.

        Returns the first matching entry, or ``None``. Not an index — linear
        scan. If hot-path performance matters the caller should build its own
        alias map from :pyattr:`alias_index`.
        """
        needle = (text or "").strip().lower()
        if not needle:
            return None
        for entry in self.entries:
            if needle in entry.alias_set:
                return entry
        return None

    @property
    def alias_index(self) -> dict[str, VocabEntry]:
        """Build a dict mapping every alias (lowercase) to its entry.

        First-writer-wins on collisions within the same pack.
        """
        out: dict[str, VocabEntry] = {}
        for entry in self.entries:
            for alias in entry.alias_set:
                out.setdefault(alias, entry)
        return out


def validate_pack_dict(raw: dict[str, Any]) -> list[str]:
    """Validate a raw pack dict and return a list of error strings.

    Empty list means the pack is schema-valid. This is a best-effort check
    focused on required fields and enum value correctness — not full JSON
    Schema validation.
    """
    errors: list[str] = []

    if not isinstance(raw, dict):
        return [f"pack root must be a mapping, got {type(raw).__name__}"]

    for required in REQUIRED_PACK_FIELDS:
        if required not in raw:
            errors.append(f"missing required pack field: {required}")

    release_tier = raw.get("release_tier")
    if release_tier is not None and release_tier not in VALID_RELEASE_TIER:
        errors.append(
            f"release_tier {release_tier!r} not in {sorted(VALID_RELEASE_TIER)}"
        )

    entries = raw.get("entries")
    if entries is None:
        return errors
    if not isinstance(entries, list):
        errors.append(f"entries must be a list, got {type(entries).__name__}")
        return errors
    if not entries:
        errors.append("entries list is empty")
        return errors

    defaults = raw.get("entry_defaults") or {}

    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry #{idx} must be a mapping")
            continue

        prefix = f"entry #{idx} ({entry.get('term_id', '<no term_id>')})"

        for required in REQUIRED_ENTRY_FIELDS:
            if required not in entry or entry[required] in (None, ""):
                errors.append(f"{prefix}: missing required field {required}")

        kind = entry.get("kind")
        if kind is not None and kind not in VALID_KIND:
            errors.append(f"{prefix}: kind {kind!r} not in {sorted(VALID_KIND)}")

        collision_risk = entry.get("collision_risk", defaults.get("collision_risk"))
        if collision_risk is None:
            errors.append(f"{prefix}: missing collision_risk (and no default)")
        elif collision_risk not in VALID_COLLISION_RISK:
            errors.append(
                f"{prefix}: collision_risk {collision_risk!r} not in "
                f"{sorted(VALID_COLLISION_RISK)}"
            )

        source_kind = entry.get("source_kind", defaults.get("source_kind"))
        if source_kind is None:
            errors.append(f"{prefix}: missing source_kind (and no default)")
        elif source_kind not in VALID_SOURCE_KIND:
            errors.append(
                f"{prefix}: source_kind {source_kind!r} not in "
                f"{sorted(VALID_SOURCE_KIND)}"
            )

        sources = entry.get("sources", defaults.get("sources"))
        if not sources:
            errors.append(f"{prefix}: sources list missing or empty")
        elif not isinstance(sources, list):
            errors.append(f"{prefix}: sources must be a list")
        else:
            for s_idx, src in enumerate(sources):
                if not isinstance(src, dict):
                    errors.append(f"{prefix}: source #{s_idx} must be a mapping")
                    continue
                if not src.get("source_id"):
                    errors.append(f"{prefix}: source #{s_idx} missing source_id")
                if not src.get("citation"):
                    errors.append(f"{prefix}: source #{s_idx} missing citation")

        for bool_field in ("regex_safe", "retrieval_expand"):
            val = entry.get(bool_field, defaults.get(bool_field))
            if val is None:
                errors.append(f"{prefix}: missing {bool_field} (and no default)")
            elif not isinstance(val, bool):
                errors.append(
                    f"{prefix}: {bool_field} must be a bool, got "
                    f"{type(val).__name__}"
                )

    return errors


def _coerce_entry(raw: dict[str, Any], defaults: dict[str, Any]) -> VocabEntry:
    """Convert a raw dict into a :class:`VocabEntry`, applying pack-level defaults."""
    core_fields = {
        "term_id",
        "canonical",
        "kind",
        "domain",
        "category",
        "aliases",
        "expansion",
        "definition_short",
        "regex_safe",
        "retrieval_expand",
        "collision_risk",
        "source_kind",
        "sources",
        "confidence",
        "notes",
    }

    def pick(name: str, fallback: Any = None) -> Any:
        if name in raw and raw[name] is not None:
            return raw[name]
        return defaults.get(name, fallback)

    extras = {
        k: v
        for k, v in raw.items()
        if k not in core_fields and v is not None
    }

    return VocabEntry(
        term_id=str(raw["term_id"]),
        canonical=str(raw["canonical"]),
        kind=str(raw["kind"]),
        domain=str(raw["domain"]),
        category=str(raw["category"]),
        regex_safe=bool(pick("regex_safe", False)),
        retrieval_expand=bool(pick("retrieval_expand", True)),
        collision_risk=str(pick("collision_risk", "medium")),
        source_kind=str(pick("source_kind", "official_public")),
        sources=list(pick("sources", []) or []),
        aliases=list(raw.get("aliases") or []),
        expansion=str(raw.get("expansion") or ""),
        definition_short=str(raw.get("definition_short") or ""),
        confidence=str(raw.get("confidence") or ""),
        notes=str(raw.get("notes") or ""),
        extras=extras,
    )


def load_pack(path: str | Path) -> VocabPack:
    """Load and validate a single vocabulary pack from a YAML file.

    Raises :class:`VocabPackError` if the file is missing, unparsable, or
    schema-invalid.
    """
    pack_path = Path(path)
    if not pack_path.exists():
        raise VocabPackError(f"vocab pack not found: {pack_path}")

    try:
        with open(pack_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise VocabPackError(f"YAML parse error in {pack_path}: {exc}") from exc

    if raw is None:
        raise VocabPackError(f"vocab pack is empty: {pack_path}")

    errors = validate_pack_dict(raw)
    if errors:
        joined = "\n  - ".join(errors)
        raise VocabPackError(f"vocab pack {pack_path} failed validation:\n  - {joined}")

    defaults = raw.get("entry_defaults") or {}
    entries = [_coerce_entry(e, defaults) for e in raw["entries"]]

    return VocabPack(
        pack_id=str(raw["pack_id"]),
        pack_name=str(raw["pack_name"]),
        domain=str(raw["domain"]),
        version=str(raw["version"]),
        release_tier=str(raw["release_tier"]),
        status=str(raw["status"]),
        entries=entries,
        description=str(raw.get("description") or ""),
        provenance=dict(raw.get("provenance") or {}),
        entry_defaults=dict(defaults),
        source_path=str(pack_path),
    )


def load_all_packs(directory: str | Path) -> list[VocabPack]:
    """Load every ``*.yaml`` pack under ``directory`` (non-recursive).

    Returns the loaded packs sorted by ``pack_id``. Raises
    :class:`VocabPackError` on the first invalid pack encountered, so a
    malformed pack is always a hard failure — never silent degradation.
    """
    root = Path(directory)
    if not root.exists():
        raise VocabPackError(f"vocab pack directory not found: {root}")
    if not root.is_dir():
        raise VocabPackError(f"vocab pack path is not a directory: {root}")

    packs: list[VocabPack] = []
    for pack_file in sorted(root.glob("*.yaml")):
        packs.append(load_pack(pack_file))
    packs.sort(key=lambda p: p.pack_id)
    return packs


def _normalize_column_token(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = " ".join(text.replace("_", " ").split())
    return text


def _column_token_variants(value: str) -> set[str]:
    normalized = _normalize_column_token(value)
    if not normalized:
        return set()
    compact = "".join(ch for ch in normalized if ch.isalnum())
    return {normalized, compact}


@lru_cache(maxsize=4)
def load_column_aliases(path: str | Path) -> dict[str, tuple[str, ...]]:
    alias_path = Path(path)
    if not alias_path.exists():
        raise VocabPackError(f"column alias file not found: {alias_path}")
    try:
        with open(alias_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise VocabPackError(f"YAML parse error in {alias_path}: {exc}") from exc

    concepts = raw.get("concepts")
    if not isinstance(concepts, dict) or not concepts:
        raise VocabPackError(f"column alias file missing non-empty concepts map: {alias_path}")

    resolved: dict[str, tuple[str, ...]] = {}
    for concept, aliases in concepts.items():
        if not isinstance(aliases, list) or not aliases:
            raise VocabPackError(f"column alias concept {concept!r} must map to a non-empty list")
        normalized_aliases = []
        for alias in aliases:
            alias_text = str(alias or "").strip()
            if alias_text:
                normalized_aliases.append(alias_text)
        if not normalized_aliases:
            raise VocabPackError(f"column alias concept {concept!r} has no usable aliases")
        resolved[str(concept)] = tuple(normalized_aliases)
    return resolved


def resolve_column(
    header: str,
    concept: str,
    aliases_path: str | Path = "config/column_aliases.yaml",
) -> str:
    """Return ``concept`` when a header maps to it via the column-alias file.

    This is a lightweight portability helper for structured workbook parsing.
    It intentionally lives in ``pack_loader`` so callers can stay on one
    deterministic vocabulary interface instead of hardcoding ad-hoc header maps.
    """
    header_variants = _column_token_variants(header)
    if not header_variants:
        return ""
    concepts = load_column_aliases(Path(aliases_path))
    aliases = concepts.get(concept, ())
    for alias in aliases:
        if header_variants & _column_token_variants(alias):
            return concept
    return ""
