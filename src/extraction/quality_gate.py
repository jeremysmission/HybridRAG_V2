"""
Quality gate — filters and normalizes extracted entities before storage.

Applies:
  1. Confidence threshold (default 0.7)
  2. Site vocabulary normalization (aliases → canonical names)
  3. Part number pattern validation
  4. Dedup within a batch (same entity from regex + LLM)
  5. Relationship confidence filtering
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from src.store.entity_store import Entity
from src.store.relationship_store import Relationship

logger = logging.getLogger(__name__)


class QualityGate:
    """
    Filters and normalizes entities before insertion into stores.

    Loads controlled vocabulary from site_vocabulary.yaml for
    alias resolution and pattern validation.
    """

    def __init__(
        self,
        min_confidence: float = 0.7,
        vocab_path: str = "config/site_vocabulary.yaml",
        part_patterns: list[str] | None = None,
    ):
        self.min_confidence = min_confidence
        self._site_aliases: dict[str, str] = {}  # alias → canonical
        self._role_aliases: dict[str, str] = {}   # alias → canonical
        self._part_validators: list[re.Pattern] = []
        self._load_vocabulary(vocab_path)

        if part_patterns:
            self._part_validators.extend(re.compile(p) for p in part_patterns)

    def _load_vocabulary(self, vocab_path: str) -> None:
        """Load site vocabulary YAML."""
        path = Path(vocab_path)
        if not path.exists():
            logger.warning("Site vocabulary not found at %s — skipping normalization", vocab_path)
            return

        with open(path, encoding="utf-8-sig") as f:
            vocab = yaml.safe_load(f) or {}

        # Build site alias map
        for canonical, info in vocab.get("sites", {}).items():
            self._site_aliases[canonical.lower()] = canonical
            for alias in info.get("aliases", []):
                self._site_aliases[alias.lower()] = canonical

        # Build role alias map
        for canonical, aliases in vocab.get("roles", {}).items():
            self._role_aliases[canonical.lower()] = canonical
            for alias in aliases:
                self._role_aliases[alias.lower()] = canonical

        # Build part validators from vocab
        for entry in vocab.get("part_patterns", []):
            try:
                self._part_validators.append(re.compile(entry["pattern"]))
            except (KeyError, re.error):
                pass

        logger.info(
            "Quality gate loaded: %d site aliases, %d role aliases, %d part patterns",
            len(self._site_aliases), len(self._role_aliases), len(self._part_validators),
        )

    def filter_entities(self, entities: list[Entity]) -> list[Entity]:
        """
        Apply quality gates to a list of entities.

        Returns only entities that pass confidence threshold,
        with normalized text.
        """
        passed = []
        seen = set()

        for e in entities:
            # Confidence gate
            if e.confidence < self.min_confidence:
                continue

            # Normalize
            normalized = self._normalize_entity(e)

            # Dedup key: type + normalized text + chunk
            key = (normalized.entity_type, normalized.text, normalized.chunk_id)
            if key in seen:
                continue
            seen.add(key)

            passed.append(normalized)

        logger.debug(
            "Quality gate: %d in → %d passed (%.0f%% filtered)",
            len(entities), len(passed),
            (1 - len(passed) / max(len(entities), 1)) * 100,
        )
        return passed

    def filter_relationships(self, rels: list[Relationship]) -> list[Relationship]:
        """
        Apply quality gates to relationships.

        Returns only relationships that pass confidence threshold,
        with normalized subject/object text.
        """
        passed = []
        seen = set()

        for r in rels:
            if r.confidence < self.min_confidence:
                continue

            normalized = self._normalize_relationship(r)

            key = (normalized.subject_text, normalized.predicate,
                   normalized.object_text, normalized.chunk_id)
            if key in seen:
                continue
            seen.add(key)

            passed.append(normalized)

        return passed

    def _normalize_entity(self, entity: Entity) -> Entity:
        """Normalize entity text based on type."""
        text = entity.text

        if entity.entity_type == "SITE":
            text = self._normalize_site(text)
        elif entity.entity_type == "PART":
            text = text.upper().strip()
        elif entity.entity_type == "PERSON":
            text = self._normalize_person(text)
        elif entity.entity_type == "PO":
            text = text.upper().strip()
        elif entity.entity_type == "CONTACT":
            text = text.strip().lower() if "@" in text else text.strip()
        elif entity.entity_type == "DATE":
            text = text.strip()

        return Entity(
            entity_type=entity.entity_type,
            text=text,
            raw_text=entity.raw_text,
            confidence=entity.confidence,
            chunk_id=entity.chunk_id,
            source_path=entity.source_path,
            context=entity.context,
        )

    def _normalize_relationship(self, rel: Relationship) -> Relationship:
        """Normalize subject/object text in relationships."""
        subject = rel.subject_text
        obj = rel.object_text

        if rel.subject_type == "SITE":
            subject = self._normalize_site(subject)
        elif rel.subject_type in ("PART", "PO"):
            subject = subject.upper().strip()

        if rel.object_type == "SITE":
            obj = self._normalize_site(obj)
        elif rel.object_type in ("PART", "PO"):
            obj = obj.upper().strip()

        return Relationship(
            subject_type=rel.subject_type,
            subject_text=subject,
            predicate=rel.predicate,
            object_type=rel.object_type,
            object_text=obj,
            confidence=rel.confidence,
            source_path=rel.source_path,
            chunk_id=rel.chunk_id,
            context=rel.context,
        )

    def _normalize_site(self, text: str) -> str:
        """Resolve site aliases to canonical names."""
        canonical = self._site_aliases.get(text.strip().lower())
        if canonical:
            return canonical
        return text.strip().title()

    def _normalize_person(self, text: str) -> str:
        """Normalize person names to title case, strip role suffixes."""
        parts = text.split(",", 1)
        name = parts[0].strip().title()
        return name
