"""
Aggregation executor — deterministic backend for failure-aggregation queries.

This is the SAG (Structure-Augmented Generation) entry point. It:

  1. Detects aggregation intent ("top N", "highest", "rank", "count") on the
     failure axis (part_number + system + site + year).
  2. Parses filter parameters from the natural-language query.
  3. Runs a parameterized SQL GROUP BY against failure_events.
  4. Links evidence rows back to source chunks.
  5. Returns a pre-rendered StructuredResult that the LLM narrates
     but never re-computes.

Three tier outcomes:
  GREEN  — deterministic exact ranking returned
  YELLOW — substrate partial (e.g. no denominator for rate); counts only
  RED    — insufficient substrate; return UNSUPPORTED
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.extraction.failure_event_extractor import extract_part_numbers
from src.store.failure_events_store import FailureEventsStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

_AGG_TRIGGERS = (
    re.compile(r"\btop\s+\d+\b",                re.IGNORECASE),
    re.compile(r"\btop\s+(?:five|ten|three|seven)\b", re.IGNORECASE),
    re.compile(r"\btop\s+(?:failing|failed|failure|failures)\b", re.IGNORECASE),
    re.compile(r"\bhighest\b",                  re.IGNORECASE),
    re.compile(r"\bmost[\s-]+(?:failing|failed|failure)\b", re.IGNORECASE),
    re.compile(r"\brank(?:ed|ing)?\b",          re.IGNORECASE),
    re.compile(r"\bwhich\s+part\s+numbers?\b",  re.IGNORECASE),
    re.compile(r"\bwhat\s+were\s+the\s+(?:highest|top|most)\b", re.IGNORECASE),
)

_FAILURE_AXIS = re.compile(
    r"\b(failing|failed|failure|failures|failure\s+rate)\b",
    re.IGNORECASE,
)

_PER_YEAR_SHAPE = re.compile(
    r"\b(each\s+year|per\s+year|every\s+year|by\s+year|ranked\s+each\s+year)\b",
    re.IGNORECASE,
)

_INVENTORY_TRIGGERS = (
    re.compile(r"\breorder\s+point\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+should\s+(?:our|we)\s+stock\b", re.IGNORECASE),
    re.compile(r"\binventory\s+for\b", re.IGNORECASE),
)

_INVENTORY_SITE_HINT = re.compile(r"\b(?:at|for|in)\b", re.IGNORECASE)
_INVENTORY_SYSTEM_WIDE = re.compile(
    r"\bacross\s+all(?:\s+[A-Za-z0-9_-]+)?\s+sites\b",
    re.IGNORECASE,
)
_EXPOSURE_TRIGGERS = (
    re.compile(r"\bexposure\s+per\s+site\b", re.IGNORECASE),
    re.compile(r"\btotal\s+exposure\b", re.IGNORECASE),
    re.compile(r"\breplacement[-\s]+cost\s+exposure\b", re.IGNORECASE),
    re.compile(r"\bwhat(?:'s|\s+is)\s+our\s+total\s+exposure\b", re.IGNORECASE),
)
_RISK_TRIGGERS = (
    re.compile(r"\bparts?\s+at\s+risk\b", re.IGNORECASE),
    re.compile(r"\bmost\s+at\s+risk\b", re.IGNORECASE),
)
_HOSTILE_QUERY_PAT = re.compile(
    r"(?:;\s*(?:drop|delete|insert|update|alter|create|attach|detach|pragma|union|select)\b"
    r"|--|/\*|\*/|\bunion\s+select\b|\bor\s+1\s*=\s*1\b)",
    re.IGNORECASE,
)

_DEFAULT_LEAD_TIME_DAYS = 90
_SERVICE_LEVEL_Z = 1.65
_ABC_Z_VALUES = {
    "A": 2.33,
    "B": 1.65,
    "C": 1.28,
    "UNKNOWN": 1.65,
}


def detect_aggregation_intent(query: str) -> bool:
    """Return True if query looks like failure-aggregation intent."""
    if not query:
        return False
    has_trigger = any(p.search(query) for p in _AGG_TRIGGERS)
    has_failure = bool(_FAILURE_AXIS.search(query))
    return has_trigger and has_failure


def detect_inventory_intent(query: str) -> bool:
    """Return True if query looks like reorder-point / stocking intent."""
    if not query:
        return False
    has_trigger = any(p.search(query) for p in _INVENTORY_TRIGGERS)
    has_site_hint = bool(_INVENTORY_SITE_HINT.search(query) or _INVENTORY_SYSTEM_WIDE.search(query))
    return has_trigger and has_site_hint


def detect_inventory_rollup_intent(query: str) -> bool:
    """Return True for live multi-site exposure / risk inventory queries."""
    if not query:
        return False
    return any(p.search(query) for p in (*_EXPOSURE_TRIGGERS, *_RISK_TRIGGERS))


# ---------------------------------------------------------------------------
# Filter parsing
# ---------------------------------------------------------------------------

_NUM_WORDS = {"one": 1, "three": 3, "five": 5, "seven": 7, "ten": 10}


def parse_top_n(query: str, default: int = 5) -> int:
    m = re.search(r"\btop\s+(\d+)\b", query, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        return max(1, min(50, n))
    m = re.search(r"\btop\s+(one|three|five|seven|ten)\b", query, re.IGNORECASE)
    if m:
        return _NUM_WORDS.get(m.group(1).lower(), default)
    return default


def parse_year_range(query: str) -> tuple[int | None, int | None]:
    """
    Accepts shapes like:
      - "in 2024"                    → (2024, 2024)
      - "from 2022-2025"             → (2022, 2025)
      - "between 2022 and 2025"      → (2022, 2025)
      - "past 7 years"               → (current-6, current) — current assumed 2025
      - "each year for the past 7"   → (2019, 2025)
    """
    if not query:
        return (None, None)

    m = re.search(r"\b(20[0-3]\d)\s*(?:-|to|through|thru)\s*(20[0-3]\d)\b", query)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    m = re.search(r"\bbetween\s+(20[0-3]\d)\s+and\s+(20[0-3]\d)\b", query, re.IGNORECASE)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    m = re.search(r"\bpast\s+(\d+)\s+years?\b", query, re.IGNORECASE)
    if m:
        span = int(m.group(1))
        # Anchor to 2025 as "current" (corpus latest year is 2025)
        return (2025 - span + 1, 2025)

    m = re.search(r"\bin\s+(20[0-3]\d)\b", query, re.IGNORECASE)
    if m:
        y = int(m.group(1))
        return (y, y)

    m = re.search(r"\b(FY|CY)\s*(20\d{2}|\d{2})\b", query, re.IGNORECASE)
    if m:
        raw = m.group(2)
        y = int(raw) if len(raw) == 4 else (2000 + int(raw) if int(raw) <= 49 else 1900 + int(raw))
        return (y, y)

    return (None, None)


# ---------------------------------------------------------------------------
# Alias resolution from canonical_aliases.yaml
# ---------------------------------------------------------------------------

@dataclass
class AliasTables:
    system_to_aliases: dict[str, list[str]] = field(default_factory=dict)
    site_aliases: dict[str, list[str]] = field(default_factory=dict)  # canonical_token → aliases
    site_alias_lookup: dict[str, str] = field(default_factory=dict)   # alias → canonical_token

    @classmethod
    def load(cls, yaml_path: str | Path) -> "AliasTables":
        path = Path(yaml_path)
        if not path.exists():
            logger.warning("canonical_aliases.yaml not found at %s — using defaults", path)
            return cls()
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        systems = {
            canon: [canon] + list(info.get("aliases", []))
            for canon, info in (data.get("systems") or {}).items()
        }
        sites: dict[str, list[str]] = {}
        lookup: dict[str, str] = {}
        for canon_token, info in (data.get("sites") or {}).items():
            aliases = [canon_token] + list(info.get("aliases", []))
            sites[canon_token] = aliases
            for al in aliases:
                lookup[al.lower()] = canon_token
        return cls(system_to_aliases=systems, site_aliases=sites, site_alias_lookup=lookup)

    def has_systems_configured(self) -> bool:
        """True when the alias table has at least one system + its aliases
        loaded from config. Used as a fail-closed gate: if False, aggregation
        intent should not proceed because the canonical source of truth is
        missing."""
        return bool(self.system_to_aliases)

    def resolve_system(self, query: str) -> str:
        q = query.lower()
        for canon, aliases in self.system_to_aliases.items():
            for al in aliases:
                if re.search(rf"\b{re.escape(al.lower())}\b", q):
                    return canon
        return ""

    def resolve_site(self, query: str) -> str:
        q = query.lower()
        # Prefer longest alias match to avoid "ge" matching "georgia"
        best = ""
        best_len = 0
        for alias, canon in self.site_alias_lookup.items():
            if re.search(rf"\b{re.escape(alias)}\b", q):
                if len(alias) > best_len:
                    best = canon
                    best_len = len(alias)
        return best


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AggregationResult:
    tier: str                         # GREEN | YELLOW | RED
    query: str
    parsed_params: dict[str, Any]
    ranked_rows: list[dict]
    per_year_rows: dict[int, list[dict]]  # empty dict when not per-year
    evidence_by_part: dict[str, list[dict]]
    substrate_coverage: dict[str, Any]
    context_text: str
    sources: list[str]
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "query": self.query,
            "parsed_params": self.parsed_params,
            "ranked_rows": self.ranked_rows,
            "per_year_rows": self.per_year_rows,
            "evidence_by_part": self.evidence_by_part,
            "substrate_coverage": self.substrate_coverage,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class AggregationExecutor:
    """Runs deterministic failure-aggregation SQL + builds context for the LLM."""

    def __init__(
        self,
        failure_store: FailureEventsStore,
        aliases: AliasTables,
        po_db_path: str | Path | None = None,
        installed_base_db_path: str | Path | None = None,
    ):
        self.store = failure_store
        self.aliases = aliases
        self.po_db_path = Path(po_db_path) if po_db_path else None
        self.installed_base_db_path = (
            Path(installed_base_db_path) if installed_base_db_path else None
        )

    def try_execute(self, query: str) -> AggregationResult | None:
        """Return AggregationResult if query matches, else None (fall through to RAG).

        Fails closed when the canonical alias config is missing entirely —
        aggregation is a contract-bound feature, and without the canonical
        source of truth we refuse to run rather than silently substituting.
        """
        if detect_inventory_intent(query):
            return self.execute_inventory(query)
        if detect_inventory_rollup_intent(query):
            return self.execute_inventory_rollup(query)
        if not detect_aggregation_intent(query):
            return None
        if not self.aliases.has_systems_configured():
            logger.warning(
                "AggregationExecutor: canonical_aliases.yaml missing or empty — "
                "failing closed (passthrough to RAG). Query: %s",
                query,
            )
            return None
        return self.execute(query)

    def execute(self, query: str) -> AggregationResult:
        top_n = parse_top_n(query)
        year_from, year_to = parse_year_range(query)
        system = self.aliases.resolve_system(query)
        site = self.aliases.resolve_site(query)
        # Narrow substrate-fallback path: the aliases YAML is known to be loaded
        # (we passed the has_systems_configured gate in try_execute), but a
        # particular system/site term may not be in the alias list yet. When
        # that happens, fall back to literal-match against values actually
        # present in failure_events. This is NOT a fail-open; it's robustness
        # against an incomplete-but-present alias config.
        if not system:
            q_lower = query.lower()
            for sys_name in self.store.distinct_systems():
                if sys_name and re.search(
                    rf"\b{re.escape(sys_name.lower())}\b", q_lower
                ):
                    system = sys_name
                    break
        if not site:
            q_lower = query.lower()
            try:
                rows = self.store._conn.execute(
                    "SELECT DISTINCT site_token FROM failure_events "
                    "WHERE site_token != ''"
                ).fetchall()
                distinct_sites = [r[0] for r in rows]
            except Exception:
                distinct_sites = []
            for site_name in distinct_sites:
                if re.search(rf"\b{re.escape(site_name.lower())}\b", q_lower):
                    site = site_name
                    break
        # Unknown-system / unknown-site detection: if the query references a
        # system- or site-shaped token that we couldn't resolve, fail RED
        # rather than silently dropping the filter and returning global results.
        unresolved_system = _detect_unresolved_system_reference(
            query, system, self.aliases.system_to_aliases,
            {s.upper() for s in self.store.distinct_systems() if s},
            known_parts={p.upper() for p in extract_part_numbers(query, max_parts=5)},
        )
        unresolved_site = _detect_unresolved_site_reference(
            query, site, self.aliases.site_alias_lookup,
            {s.lower() for s in self._distinct_sites() if s},
            known_systems={c.upper() for c in self.aliases.system_to_aliases}
                          | {s.upper() for s in self.store.distinct_systems() if s},
        )
        per_year = bool(_PER_YEAR_SHAPE.search(query))
        is_rate = bool(re.search(r"\bfailure\s+rate\b", query, re.IGNORECASE))

        parsed = {
            "top_n": top_n,
            "year_from": year_from,
            "year_to": year_to,
            "system": system,
            "site_token": site,
            "per_year": per_year,
            "is_rate": is_rate,
        }

        coverage = self.store.coverage_summary()
        parsed_params = {**parsed, "coverage": coverage}

        # RED — substrate empty
        if coverage.get("total_events", 0) == 0:
            return self._red(query, parsed_params,
                             "failure_events substrate is empty — run scripts/populate_failure_events.py")

        # RED — user referenced an unknown system/site that we cannot resolve.
        # Prevents silent filter-drop from returning misleading global top-N.
        if unresolved_system:
            return self._red(
                query, parsed_params,
                f"query references unknown system '{unresolved_system}' — "
                f"not present in canonical_aliases.yaml or failure_events substrate",
            )
        if unresolved_site:
            return self._red(
                query, parsed_params,
                f"query references unknown site '{unresolved_site}' — "
                f"not present in canonical_aliases.yaml or failure_events substrate",
            )

        # Per-year top-N shape
        if per_year and year_from is not None and year_to is not None:
            per_year_rows = self.store.top_n_parts_per_year(
                system=system or None,
                site_token=site or None,
                year_from=year_from,
                year_to=year_to,
                limit_per_year=top_n,
            )
            if not per_year_rows:
                return self._red(query, parsed_params,
                                 "no failure events match filters for per-year ranking")
            evidence = self._collect_evidence_per_year(per_year_rows, system, site)
            tier = "YELLOW" if is_rate else "GREEN"
            text, sources = self._render_per_year(query, per_year_rows, evidence, parsed_params, tier)
            return AggregationResult(
                tier=tier,
                query=query,
                parsed_params=parsed_params,
                ranked_rows=[],
                per_year_rows=per_year_rows,
                evidence_by_part=evidence,
                substrate_coverage=coverage,
                context_text=text,
                sources=sources,
                message="" if tier == "GREEN" else "failure rate requires installed-base denominator (not yet populated) — showing failure counts only",
            )

        # Single-slice top-N
        rows = self.store.top_n_parts(
            system=system or None,
            site_token=site or None,
            year_from=year_from,
            year_to=year_to,
            limit=top_n,
        )
        if not rows:
            return self._red(query, parsed_params,
                             "no failure events match the requested filters")
        evidence = {
            r["part_number"]: self.store.evidence_for_part(
                r["part_number"],
                system=system or None, site_token=site or None,
                year_from=year_from, year_to=year_to, limit=3,
            )
            for r in rows
        }
        tier = "YELLOW" if is_rate else "GREEN"
        text, sources = self._render_top_n(query, rows, evidence, parsed_params, tier)
        return AggregationResult(
            tier=tier,
            query=query,
            parsed_params=parsed_params,
            ranked_rows=rows,
            per_year_rows={},
            evidence_by_part=evidence,
            substrate_coverage=coverage,
            context_text=text,
            sources=sources,
            message="" if tier == "GREEN" else "failure rate requires installed-base denominator (not yet populated) — showing failure counts only",
        )

    def execute_inventory(self, query: str) -> AggregationResult:
        """Inventory recommendation entry point for site and system-wide shapes."""
        part_numbers = extract_part_numbers(query, max_parts=1)
        part_number = part_numbers[0] if part_numbers else ""
        known_parts = {p.upper() for p in extract_part_numbers(query, max_parts=5)}
        system = self.aliases.resolve_system(query)
        site = self.aliases.resolve_site(query)
        inventory_scope = self._resolve_inventory_scope(query)
        hostile_reason = self._detect_hostile_inventory_input(query)
        year_from, year_to = parse_year_range(query)

        if not system:
            q_lower = query.lower()
            for sys_name in self.store.distinct_systems():
                if sys_name and re.search(rf"\b{re.escape(sys_name.lower())}\b", q_lower):
                    system = sys_name
                    break
        if not site:
            q_lower = query.lower()
            for site_name in self._distinct_sites():
                if re.search(rf"\b{re.escape(site_name.lower())}\b", q_lower):
                    site = site_name
                    break

        parsed_params: dict[str, Any] = {
            "query_mode": "INVENTORY",
            "part_number": part_number,
            "system": system,
            "site_token": site,
            "inventory_scope": inventory_scope,
            "lead_time_days": _DEFAULT_LEAD_TIME_DAYS,
            "service_level_z": _SERVICE_LEVEL_Z,
            "year_from": year_from,
            "year_to": year_to,
            "coverage": self.store.coverage_summary(),
        }

        if hostile_reason:
            return self._red(query, parsed_params, hostile_reason)
        if not part_number:
            return self._red(
                query,
                parsed_params,
                "inventory recommender requires an explicit part number in the query",
            )
        if year_from is not None and not self._inventory_year_range_supported(year_from, year_to):
            return self._red(
                query,
                parsed_params,
                f"inventory recommender year filter {year_from}–{year_to} falls outside failure_events coverage",
            )

        unresolved_system = _detect_unresolved_system_reference(
            query, system, self.aliases.system_to_aliases,
            {s.upper() for s in self.store.distinct_systems() if s},
            known_parts=known_parts,
        )
        unresolved_site = _detect_unresolved_site_reference(
            query, site, self.aliases.site_alias_lookup,
            {s.lower() for s in self._distinct_sites() if s},
            known_systems={c.upper() for c in self.aliases.system_to_aliases}
                          | {s.upper() for s in self.store.distinct_systems() if s},
        )
        if unresolved_system:
            return self._red(
                query, parsed_params,
                f"query references unknown system '{unresolved_system}' — not present in canonical aliases or failure_events",
            )
        if unresolved_site:
            return self._red(
                query, parsed_params,
                f"query references unknown site '{unresolved_site}' — not present in canonical aliases or failure_events",
            )
        if inventory_scope == "part_system_total":
            if not system:
                return self._red(
                    query,
                    parsed_params,
                    "system-wide inventory recommender requires an explicit system reference",
                )
            return self.recommend_reorder_point_live(
                part_number,
                site="",
                system=system,
                inventory_scope=inventory_scope,
                query=query,
            )
        if not site:
            return self._red(
                query,
                parsed_params,
                "inventory recommender requires an explicit site reference in the query",
            )

        return self.recommend_reorder_point(part_number, site, system, query=query)

    def execute_inventory_rollup(self, query: str) -> AggregationResult:
        """Live multi-site inventory aggregation entry point."""
        part_numbers = extract_part_numbers(query, max_parts=1)
        part_number = part_numbers[0] if part_numbers else ""
        system = self.aliases.resolve_system(query)
        site = self.aliases.resolve_site(query)
        hostile_reason = self._detect_hostile_inventory_input(query)
        year_from, year_to = parse_year_range(query)
        parsed_params: dict[str, Any] = {
            "query_mode": "AGGREGATION",
            "part_number": part_number,
            "system": system,
            "site_token": site,
            "year_from": year_from,
            "year_to": year_to,
            "coverage": self.store.coverage_summary(),
        }
        if hostile_reason:
            return self._red(query, parsed_params, hostile_reason)
        if year_from is not None and not self._inventory_year_range_supported(year_from, year_to):
            return self._red(
                query,
                parsed_params,
                f"inventory aggregation year filter {year_from}–{year_to} falls outside failure_events coverage",
            )

        if any(p.search(query) for p in _EXPOSURE_TRIGGERS):
            if not part_number:
                return self._red(
                    query,
                    parsed_params,
                    "exposure-per-site aggregation requires an explicit part number in the query",
                )
            return self.exposure_per_site(part_number, system=system, query=query)

        if any(p.search(query) for p in _RISK_TRIGGERS):
            if not site:
                return self._red(
                    query,
                    parsed_params,
                    "parts-at-risk aggregation requires an explicit site reference in the query",
                )
            return self.parts_at_risk(site, system=system, query=query)

        return self._red(query, parsed_params, "unsupported inventory aggregation shape")

    def recommend_reorder_point(
        self,
        part_number: str,
        site: str,
        system: str = "",
        *,
        query: str | None = None,
    ) -> AggregationResult:
        """Return reorder-point recommendation using stub-mode failure history."""
        history = self.store.monthly_failure_history(
            part_number,
            system=system or None,
            site_token=site or None,
            trailing_months=24,
        )
        months_history = int(history.get("span_months", 0) or 0)
        window_months = int(history.get("window_months", 0) or 0)
        month_counts = [int(v) for v in (history.get("month_counts") or [])]
        total_failures = int(history.get("total_failures", 0) or 0)

        parsed_params: dict[str, Any] = {
            "query_mode": "INVENTORY",
            "part_number": part_number,
            "system": system,
            "site_token": site,
            "lead_time_days": _DEFAULT_LEAD_TIME_DAYS,
            "service_level_z": _SERVICE_LEVEL_Z,
            "history_months": months_history,
            "window_months": window_months,
            "month_labels": history.get("month_labels") or [],
            "coverage": self.store.coverage_summary(),
        }

        if months_history < 12:
            return self._red(
                query or f"reorder point for {part_number} at {site}",
                parsed_params,
                f"inventory recommender needs at least 12 months of history; found {months_history}",
            )

        demand_rate = 0.0
        if window_months > 0:
            annualized_failures = total_failures * (12.0 / window_months)
            demand_rate = annualized_failures / 365.0
        monthly_sigma = (
            float(statistics.stdev(month_counts))
            if len(month_counts) >= 2 else 0.0
        )
        safety_stock = _SERVICE_LEVEL_Z * monthly_sigma * math.sqrt(_DEFAULT_LEAD_TIME_DAYS)
        reorder_point = (demand_rate * _DEFAULT_LEAD_TIME_DAYS) + safety_stock
        recommended_units = max(1, math.ceil(reorder_point))
        tier = "GREEN" if months_history >= 24 else "YELLOW"

        row = {
            "part_number": part_number,
            "system": system,
            "site_token": site,
            "history_months": months_history,
            "window_months": window_months,
            "total_failures": total_failures,
            "daily_demand_rate": demand_rate,
            "monthly_sigma": monthly_sigma,
            "lead_time_days": _DEFAULT_LEAD_TIME_DAYS,
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "recommended_units": recommended_units,
        }
        evidence = {
            part_number: self.store.evidence_for_part(
                part_number,
                system=system or None,
                site_token=site or None,
                limit=5,
            )
        }
        text, sources = self._render_inventory_recommendation(
            query or f"What should our reorder point be for {part_number} at {site}?",
            row=row,
            evidence=evidence,
            parsed=parsed_params,
            tier=tier,
        )
        note = (
            "stub mode: lead_time_days=90 placeholder from coordinator; installed-base normalization not yet available"
        )
        if tier == "YELLOW":
            note = (
                f"{note}; only {months_history} months of history available, so recommendation is provisional"
            )
        return AggregationResult(
            tier=tier,
            query=query or f"reorder point for {part_number} at {site}",
            parsed_params=parsed_params,
            ranked_rows=[row],
            per_year_rows={},
            evidence_by_part=evidence,
            substrate_coverage=parsed_params["coverage"],
            context_text=text,
            sources=sources,
            message=note,
        )

    def recommend_reorder_point_live(
        self,
        part_number: str,
        *,
        site: str,
        system: str = "",
        inventory_scope: str = "site_total",
        query: str | None = None,
    ) -> AggregationResult:
        """Real-mode reorder-point recommendation using live po_pricing + installed_base."""
        history = self.store.monthly_failure_history(
            part_number,
            system=system or None,
            site_token=(site or None) if inventory_scope != "part_system_total" else None,
            trailing_months=24,
        )
        months_history = int(history.get("span_months", 0) or 0)
        window_months = int(history.get("window_months", 0) or 0)
        month_counts = [int(v) for v in (history.get("month_counts") or [])]
        total_failures = int(history.get("total_failures", 0) or 0)
        profile = self._load_po_part_profile(part_number)
        abc_tier = str(profile.get("abc_tier") or "UNKNOWN")
        service_level_z = float(_ABC_Z_VALUES.get(abc_tier, _SERVICE_LEVEL_Z))
        lead_time_days = int(profile.get("lead_time_days") or _DEFAULT_LEAD_TIME_DAYS)
        installed_count = self._resolve_live_installed_count(
            part_number=part_number,
            system=system,
            site_token=site,
            inventory_scope=inventory_scope,
        )
        evidence = {
            part_number: self.store.evidence_for_part(
                part_number,
                system=system or None,
                site_token=(site or None) if inventory_scope != "part_system_total" else None,
                limit=5,
            )
        }
        parsed_params: dict[str, Any] = {
            "query_mode": "INVENTORY",
            "part_number": part_number,
            "system": system,
            "site_token": site,
            "inventory_scope": inventory_scope,
            "lead_time_days": lead_time_days,
            "service_level_z": service_level_z,
            "abc_tier": abc_tier,
            "history_months": months_history,
            "window_months": window_months,
            "month_labels": history.get("month_labels") or [],
            "coverage": self.store.coverage_summary(),
        }

        label = f"{part_number} in {system or 'any'}"
        if inventory_scope != "part_system_total":
            label = f"{part_number} at {site}"
        if months_history == 0:
            return self._red(
                query or f"reorder point for {label}",
                parsed_params,
                f"no failure history found for part_number '{part_number}' under the requested filters",
            )
        if months_history < 12:
            return self._red(
                query or f"reorder point for {label}",
                parsed_params,
                f"inventory recommender needs at least 12 months of history; found {months_history}",
            )
        if not installed_count or installed_count <= 0:
            reason = (
                f"installed base unavailable for requested part/system slice '{part_number}' / '{system or 'any'}'"
                if inventory_scope == "part_system_total"
                else f"installed base unavailable for requested site/system slice '{site}' / '{system or 'any'}'"
            )
            return self._red(query or f"reorder point for {label}", parsed_params, reason)

        annualized_failures = total_failures * (12.0 / window_months) if window_months > 0 else 0.0
        daily_demand_rate = (annualized_failures / float(installed_count)) / 365.0
        normalized_month_counts = [count / float(installed_count) for count in month_counts]
        monthly_sigma = float(statistics.stdev(normalized_month_counts)) if len(normalized_month_counts) >= 2 else 0.0
        safety_stock = service_level_z * monthly_sigma * math.sqrt(lead_time_days)
        reorder_point = (daily_demand_rate * lead_time_days) + safety_stock
        recommended_units = max(1, math.ceil(reorder_point))
        tier = "GREEN" if months_history >= 24 else "YELLOW"
        row = {
            "part_number": part_number,
            "system": system,
            "site_token": site,
            "inventory_scope": inventory_scope,
            "history_months": months_history,
            "window_months": window_months,
            "total_failures": total_failures,
            "installed_count": installed_count,
            "daily_demand_rate": daily_demand_rate,
            "monthly_sigma": monthly_sigma,
            "lead_time_days": lead_time_days,
            "service_level_z": service_level_z,
            "abc_tier": abc_tier,
            "avg_unit_price": float(profile.get("avg_unit_price") or 0.0),
            "safety_stock": safety_stock,
            "reorder_point": reorder_point,
            "recommended_units": recommended_units,
        }
        text, sources = self._render_live_inventory_recommendation(
            query or f"reorder point for {label}",
            row=row,
            evidence=evidence,
            parsed=parsed_params,
            tier=tier,
        )
        note = (
            f"real mode: lead_time_days={lead_time_days} from po_pricing when available; "
            f"installed-base denominator={installed_count}; abc_tier={abc_tier}"
        )
        if tier == "YELLOW":
            note = f"{note}; only {months_history} months of history available, so recommendation is provisional"
        return AggregationResult(
            tier=tier,
            query=query or f"reorder point for {label}",
            parsed_params=parsed_params,
            ranked_rows=[row],
            per_year_rows={},
            evidence_by_part=evidence,
            substrate_coverage=parsed_params["coverage"],
            context_text=text,
            sources=sources,
            message=note,
        )

    def exposure_per_site(
        self,
        part_number: str,
        *,
        system: str = "",
        query: str | None = None,
    ) -> AggregationResult:
        """Return installed-base exposure per site for a part using live substrates."""
        rows = self._latest_installed_rows_for_part(part_number=part_number, system=system)
        profile = self._load_po_part_profile(part_number)
        avg_unit_price = float(profile.get("avg_unit_price") or 0.0)
        lead_time_days = int(profile.get("lead_time_days") or _DEFAULT_LEAD_TIME_DAYS)
        abc_tier = str(profile.get("abc_tier") or "UNKNOWN")
        parsed_params: dict[str, Any] = {
            "query_mode": "AGGREGATION",
            "part_number": part_number,
            "system": system,
            "site_token": "",
            "aggregation_mode": "EXPOSURE_PER_SITE",
            "coverage": self.store.coverage_summary(),
        }
        if not rows:
            return self._red(
                query or f"exposure per site for {part_number}",
                parsed_params,
                f"installed base unavailable for part_number '{part_number}' under the requested filters",
            )
        ranked_rows: list[dict[str, Any]] = []
        sources: list[str] = []
        total_installed_qty = 0
        total_exposure_cost = 0.0
        for row in rows:
            installed_qty = int(row["quantity_at_site"] or 0)
            exposure_cost = installed_qty * avg_unit_price
            total_installed_qty += installed_qty
            total_exposure_cost += exposure_cost
            if row["source_path"]:
                sources.append(str(row["source_path"]))
            ranked_rows.append(
                {
                    "part_number": part_number,
                    "system": str(row["system"] or ""),
                    "site_token": str(row["site_token"] or ""),
                    "installed_qty": installed_qty,
                    "lead_time_days": lead_time_days,
                    "abc_tier": abc_tier,
                    "avg_unit_price": avg_unit_price,
                    "exposure_cost": exposure_cost,
                    "source_path": str(row["source_path"] or ""),
                }
            )
        ranked_rows.sort(key=lambda item: (-float(item["exposure_cost"]), -int(item["installed_qty"]), item["site_token"]))
        summary_row = {
            "part_number": part_number,
            "system": system,
            "site_count": len(ranked_rows),
            "total_installed_qty": total_installed_qty,
            "total_exposure_cost": total_exposure_cost,
            "lead_time_days": lead_time_days,
            "abc_tier": abc_tier,
        }
        text, rendered_sources = self._render_exposure_per_site(
            query or f"exposure per site for {part_number}",
            rows=ranked_rows,
            parsed=parsed_params,
            summary_row=summary_row,
        )
        return AggregationResult(
            tier="GREEN",
            query=query or f"exposure per site for {part_number}",
            parsed_params=parsed_params,
            ranked_rows=ranked_rows,
            per_year_rows={},
            evidence_by_part={part_number: ranked_rows[:5]},
            substrate_coverage=parsed_params["coverage"],
            context_text=text,
            sources=list(dict.fromkeys([*sources, *rendered_sources])),
            message="live installed_base x po_pricing exposure rollup",
        )

    def parts_at_risk(
        self,
        site: str,
        *,
        system: str = "",
        query: str | None = None,
    ) -> AggregationResult:
        """Return parts at site where reorder_point exceeds stock proxy."""
        site_total = self._resolve_live_installed_count(
            part_number="",
            system=system,
            site_token=site,
            inventory_scope="site_total",
        )
        parsed_params: dict[str, Any] = {
            "query_mode": "AGGREGATION",
            "part_number": "",
            "system": system,
            "site_token": site,
            "aggregation_mode": "PARTS_AT_RISK",
            "coverage": self.store.coverage_summary(),
        }
        if not site_total or site_total <= 0:
            return self._red(
                query or f"parts at risk for {site}",
                parsed_params,
                f"installed base unavailable for requested site/system slice '{site}' / '{system or 'any'}'",
            )
        rows = self._parts_at_risk_rows(site=site, system=system, site_total=site_total)
        if not rows:
            return self._red(
                query or f"parts at risk for {site}",
                parsed_params,
                "no positive risk gaps found with current stock proxy",
            )
        text, sources = self._render_parts_at_risk(
            query or f"parts at risk for {site}",
            rows=rows,
            parsed=parsed_params,
            site_total=site_total,
        )
        return AggregationResult(
            tier="GREEN",
            query=query or f"parts at risk for {site}",
            parsed_params=parsed_params,
            ranked_rows=rows,
            per_year_rows={},
            evidence_by_part={row["part_number"]: [] for row in rows[:5]},
            substrate_coverage=parsed_params["coverage"],
            context_text=text,
            sources=sources,
            message="live site risk gap rollup from failure_events x installed_base x po_pricing proxy",
        )

    # -----------------------------------------------------------------------
    # Rendering helpers
    # -----------------------------------------------------------------------

    def _collect_evidence_per_year(
        self, per_year_rows: dict[int, list[dict]], system: str, site: str,
    ) -> dict[str, list[dict]]:
        seen: dict[str, list[dict]] = {}
        for year, rows in per_year_rows.items():
            for r in rows:
                part = r["part_number"]
                if part not in seen:
                    seen[part] = self.store.evidence_for_part(
                        part, system=system or None, site_token=site or None,
                        year_from=year, year_to=year, limit=2,
                    )
        return seen

    def _render_top_n(
        self, query: str, rows: list[dict], evidence: dict[str, list[dict]],
        parsed: dict[str, Any], tier: str,
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic Failure Aggregation",
            "",
            f"**Query:** {query}",
            f"**Confidence tier:** {tier}",
            f"**Filters applied:**",
            f"- system: `{parsed.get('system') or 'any'}`",
            f"- site:   `{parsed.get('site_token') or 'any'}`",
            f"- years:  `{parsed.get('year_from')}–{parsed.get('year_to')}`"
            if parsed.get("year_from") else "- years:  `any`",
            f"- top N:  `{parsed.get('top_n')}`",
            "",
            "### Ranked Results (deterministic SQL, not LLM-computed)",
            "",
            "| Rank | Part Number | Failure Count | Distinct Docs | First→Last Year |",
            "|------|-------------|---------------|---------------|-----------------|",
        ]
        sources: list[str] = []
        for i, r in enumerate(rows, 1):
            lines.append(
                f"| {i} | `{r['part_number']}` | {r['failure_count']} | "
                f"{r['distinct_docs']} | {r['first_year'] or '-'}→{r['last_year'] or '-'} |"
            )
        lines.append("")
        lines.append("### Evidence")
        lines.append("")
        for r in rows:
            part = r["part_number"]
            lines.append(f"**{part}** ({r['failure_count']} events)")
            for ev in evidence.get(part, [])[:2]:
                sp = ev.get("source_path") or ""
                if sp:
                    sources.append(sp)
                lines.append(f"- {Path(sp).name if sp else '(no source)'} "
                             f"[year={ev.get('event_year') or '-'}, "
                             f"incident={ev.get('incident_id') or '-'}, "
                             f"confidence={ev.get('confidence', 0):.2f}]")
            lines.append("")
        lines.append(self._substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_per_year(
        self, query: str, per_year_rows: dict[int, list[dict]],
        evidence: dict[str, list[dict]], parsed: dict[str, Any], tier: str,
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic Failure Aggregation — Per-Year Ranking",
            "",
            f"**Query:** {query}",
            f"**Confidence tier:** {tier}",
            f"**Filters applied:**",
            f"- system: `{parsed.get('system') or 'any'}`",
            f"- site:   `{parsed.get('site_token') or 'any'}`",
            f"- year range: `{parsed.get('year_from')}–{parsed.get('year_to')}`",
            f"- top N per year: `{parsed.get('top_n')}`",
            "",
        ]
        sources: list[str] = []
        for year in sorted(per_year_rows.keys()):
            rows = per_year_rows[year]
            lines.append(f"### {year}")
            lines.append("")
            lines.append("| Rank | Part Number | Failure Count | Distinct Docs |")
            lines.append("|------|-------------|---------------|---------------|")
            for i, r in enumerate(rows, 1):
                lines.append(
                    f"| {i} | `{r['part_number']}` | {r['failure_count']} | {r['distinct_docs']} |"
                )
            lines.append("")
            for r in rows[:2]:
                for ev in evidence.get(r["part_number"], [])[:1]:
                    sp = ev.get("source_path") or ""
                    if sp:
                        sources.append(sp)
        lines.append(self._substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_inventory_recommendation(
        self,
        query: str,
        *,
        row: dict[str, Any],
        evidence: dict[str, list[dict]],
        parsed: dict[str, Any],
        tier: str,
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic Inventory Recommendation — Stub Mode",
            "",
            f"**Query:** {query}",
            f"**Confidence tier:** {tier}",
            "",
            "**Formula**",
            "",
            "- reorder_point = demand_rate × lead_time + safety_stock",
            "- safety_stock = Z × σ_demand × sqrt(lead_time)",
            f"- lead_time_days = `{row['lead_time_days']}` (placeholder until `po_pricing.lead_time_days` lands)",
            f"- service_level_z = `{parsed.get('service_level_z')}`",
            "",
            "**Inputs**",
            "",
            f"- part_number: `{row['part_number']}`",
            f"- site: `{row['site_token']}`",
            f"- system: `{row['system'] or 'any'}`",
            f"- history_months: `{row['history_months']}`",
            f"- window_months_used: `{row['window_months']}`",
            f"- total_failures_in_window: `{row['total_failures']}`",
            f"- daily_demand_rate: `{row['daily_demand_rate']:.6f}`",
            f"- monthly_sigma: `{row['monthly_sigma']:.4f}`",
            "",
            "**Recommendation**",
            "",
            f"- safety_stock: `{row['safety_stock']:.2f}` units",
            f"- reorder_point: `{row['reorder_point']:.2f}` units",
            f"- recommended reorder point: `{row['recommended_units']}` units",
            "",
            "**Evidence**",
            "",
        ]
        sources: list[str] = []
        for ev in evidence.get(row["part_number"], [])[:3]:
            sp = ev.get("source_path") or ""
            if sp:
                sources.append(sp)
            lines.append(
                f"- {Path(sp).name if sp else '(no source)'} "
                f"[year={ev.get('event_year') or '-'}, "
                f"incident={ev.get('incident_id') or '-'}, "
                f"confidence={ev.get('confidence', 0):.2f}]"
            )
        lines.append("")
        lines.append(
            "*Stub-mode note:* demand is derived from failure-event frequency only. "
            "Installed-base normalization and real lead times are future upgrades."
        )
        lines.append(self._substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_live_inventory_recommendation(
        self,
        query: str,
        *,
        row: dict[str, Any],
        evidence: dict[str, list[dict]],
        parsed: dict[str, Any],
        tier: str,
    ) -> tuple[str, list[str]]:
        scope_label = (
            f"across all {row['system']} sites"
            if row.get("inventory_scope") == "part_system_total"
            else f"at {row['site_token']}"
        )
        lines = [
            "## Deterministic Inventory Recommendation — Real Mode",
            "",
            f"**Query:** {query}",
            f"**Confidence tier:** {tier}",
            "",
            "**Formula**",
            "",
            "- reorder_point = demand_rate × lead_time + safety_stock",
            "- safety_stock = Z × σ_demand × sqrt(lead_time)",
            f"- lead_time_days = `{row['lead_time_days']}`",
            f"- service_level_z = `{row['service_level_z']}`",
            "",
            "**Inputs**",
            "",
            f"- part_number: `{row['part_number']}`",
            f"- scope: `{scope_label}`",
            f"- system: `{row['system'] or 'any'}`",
            f"- history_months: `{row['history_months']}`",
            f"- window_months_used: `{row['window_months']}`",
            f"- total_failures_in_window: `{row['total_failures']}`",
            f"- installed_count: `{row['installed_count']}`",
            f"- abc_tier: `{row['abc_tier']}`",
            f"- daily_demand_rate: `{row['daily_demand_rate']:.6f}`",
            f"- monthly_sigma: `{row['monthly_sigma']:.4f}`",
            "",
            "**Recommendation**",
            "",
            f"- safety_stock: `{row['safety_stock']:.2f}` units",
            f"- reorder_point: `{row['reorder_point']:.2f}` units",
            f"- recommended reorder point: `{row['recommended_units']}` units",
            "",
            "**Evidence**",
            "",
        ]
        sources: list[str] = []
        for ev in evidence.get(row["part_number"], [])[:3]:
            sp = ev.get("source_path") or ""
            if sp:
                sources.append(sp)
            lines.append(
                f"- {Path(sp).name if sp else '(no source)'} "
                f"[year={ev.get('event_year') or '-'}, "
                f"incident={ev.get('incident_id') or '-'}, "
                f"confidence={ev.get('confidence', 0):.2f}]"
            )
        lines.append("")
        lines.append(
            "*Real-mode note:* demand is normalized by installed-base quantity and uses "
            "po_pricing lead-time / ABC service-level tiers when present."
        )
        lines.append(self._cross_substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_exposure_per_site(
        self,
        query: str,
        *,
        rows: list[dict[str, Any]],
        parsed: dict[str, Any],
        summary_row: dict[str, Any],
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic Installed-Cost Exposure by Site",
            "",
            f"**Query:** {query}",
            "**Confidence tier:** GREEN",
            "",
            f"- part_number: `{summary_row['part_number']}`",
            f"- system filter: `{summary_row['system'] or 'any'}`",
            f"- abc_tier: `{summary_row['abc_tier']}`",
            f"- lead_time_days: `{summary_row['lead_time_days']}`",
            f"- total_installed_qty: `{summary_row['total_installed_qty']}`",
            f"- total_exposure_cost: `${summary_row['total_exposure_cost']:.2f}`",
            "",
            "| Rank | Site | Installed Qty | Avg Unit Price | Exposure Cost |",
            "|------|------|---------------|----------------|---------------|",
        ]
        sources: list[str] = []
        for idx, row in enumerate(rows[:10], start=1):
            lines.append(
                f"| {idx} | `{row['site_token']}` | {row['installed_qty']} | "
                f"${row['avg_unit_price']:.2f} | ${row['exposure_cost']:.2f} |"
            )
            if row.get("source_path"):
                sources.append(str(row["source_path"]))
        lines.append("")
        lines.append(self._cross_substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_parts_at_risk(
        self,
        query: str,
        *,
        rows: list[dict[str, Any]],
        parsed: dict[str, Any],
        site_total: int,
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic Parts At Risk",
            "",
            f"**Query:** {query}",
            "**Confidence tier:** GREEN",
            "",
            f"- system: `{parsed.get('system') or 'any'}`",
            f"- site: `{parsed.get('site_token')}`",
            f"- site_total_installed_qty: `{site_total}`",
            "",
            "| Rank | Part Number | Reorder Point | Current Stock Proxy | Gap Units | ABC | Lead Time |",
            "|------|-------------|---------------|---------------------|-----------|-----|-----------|",
        ]
        for idx, row in enumerate(rows[:10], start=1):
            lines.append(
                f"| {idx} | `{row['part_number']}` | {row['recommended_units']} | "
                f"{row['current_stock_proxy_qty']} | {row['gap_units']} | "
                f"{row['abc_tier']} | {row['lead_time_days']} |"
            )
        lines.append("")
        lines.append(self._cross_substrate_footer(parsed))
        return "\n".join(lines), []

    def _resolve_inventory_scope(self, query: str) -> str:
        return "part_system_total" if _INVENTORY_SYSTEM_WIDE.search(query) else "site_total"

    def _detect_hostile_inventory_input(self, query: str) -> str:
        if _HOSTILE_QUERY_PAT.search(query):
            return "hostile inventory input blocked by adversarial guard (G3)"
        return ""

    def _inventory_year_range_supported(self, year_from: int | None, year_to: int | None) -> bool:
        if year_from is None and year_to is None:
            return True
        row = self.store._conn.execute(
            "SELECT MIN(event_year), MAX(event_year) FROM failure_events WHERE event_year IS NOT NULL"
        ).fetchone()
        if not row or row[0] is None or row[1] is None:
            return False
        lo = int(row[0])
        hi = min(int(row[1]), date.today().year)
        check_from = lo if year_from is None else int(year_from)
        check_to = hi if year_to is None else int(year_to)
        return lo <= check_from <= hi and lo <= check_to <= hi

    def _open_optional_sqlite(self, db_path: Path | None) -> sqlite3.Connection | None:
        if db_path is None or not db_path.exists():
            return None
        uri = f"file:{db_path.as_posix()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def _load_po_part_profile(self, part_number: str) -> dict[str, Any]:
        profile = {
            "lead_time_days": _DEFAULT_LEAD_TIME_DAYS,
            "avg_unit_price": 0.0,
            "spend": 0.0,
            "abc_tier": "UNKNOWN",
        }
        conn = self._open_optional_sqlite(self.po_db_path)
        if conn is None:
            return profile
        try:
            row = conn.execute(
                """
                SELECT
                    AVG(CASE WHEN lead_time_days IS NOT NULL AND lead_time_days > 0 THEN lead_time_days END),
                    AVG(COALESCE(unit_price, 0)),
                    SUM(COALESCE(unit_price, 0) * COALESCE(qty, 0))
                FROM po_pricing
                WHERE part_number = ?
                """,
                (part_number,),
            ).fetchone()
            if row:
                if row[0] is not None:
                    profile["lead_time_days"] = int(round(float(row[0])))
                profile["avg_unit_price"] = float(row[1] or 0.0)
                profile["spend"] = float(row[2] or 0.0)
            abc_row = conn.execute(
                """
                WITH spend AS (
                    SELECT
                        part_number,
                        SUM(COALESCE(unit_price, 0) * COALESCE(qty, 0)) AS spend
                    FROM po_pricing
                    WHERE part_number != ''
                    GROUP BY part_number
                    HAVING spend > 0
                ),
                ranked AS (
                    SELECT
                        part_number,
                        spend,
                        ROW_NUMBER() OVER (ORDER BY spend DESC, part_number ASC) AS rn,
                        COUNT(*) OVER () AS total_parts
                    FROM spend
                )
                SELECT
                    CASE
                        WHEN rn <= CAST(CEIL(total_parts * 0.2) AS INT) THEN 'A'
                        WHEN rn <= CAST(CEIL(total_parts * 0.5) AS INT) THEN 'B'
                        ELSE 'C'
                    END AS abc_tier
                FROM ranked
                WHERE part_number = ?
                """,
                (part_number,),
            ).fetchone()
            if abc_row and abc_row[0]:
                profile["abc_tier"] = str(abc_row[0])
            return profile
        finally:
            conn.close()

    def _resolve_live_installed_count(
        self,
        *,
        part_number: str,
        system: str,
        site_token: str,
        inventory_scope: str,
    ) -> int | None:
        conn = self._open_optional_sqlite(self.installed_base_db_path)
        if conn is None:
            return None
        try:
            if inventory_scope == "part_system_total":
                clauses = ["part_number = ?", "quantity_at_site IS NOT NULL", "quantity_at_site > 0"]
                params: list[object] = [part_number]
                if system:
                    clauses.append("system = ?")
                    params.append(system)
            else:
                if not site_token:
                    return None
                clauses = [
                    "part_number != ''",
                    "quantity_at_site IS NOT NULL",
                    "quantity_at_site > 0",
                    "site_token = ?",
                ]
                params = [site_token]
                if system:
                    clauses.append("system = ?")
                    params.append(system)
            row = conn.execute(
                f"""
                WITH ranked AS (
                    SELECT
                        part_number,
                        system,
                        site_token,
                        quantity_at_site,
                        ROW_NUMBER() OVER (
                            PARTITION BY part_number, system, site_token
                            ORDER BY COALESCE(snapshot_year, 0) DESC,
                                     COALESCE(snapshot_date, '') DESC,
                                     id DESC
                        ) AS rn
                    FROM installed_base
                    WHERE {' AND '.join(clauses)}
                )
                SELECT SUM(quantity_at_site)
                FROM ranked
                WHERE rn = 1
                """,
                params,
            ).fetchone()
            if not row or row[0] is None:
                return None
            total = int(row[0] or 0)
            return total if total > 0 else None
        finally:
            conn.close()

    def _latest_installed_rows_for_part(
        self,
        *,
        part_number: str,
        system: str = "",
    ) -> list[sqlite3.Row]:
        conn = self._open_optional_sqlite(self.installed_base_db_path)
        if conn is None:
            return []
        conn.row_factory = sqlite3.Row
        try:
            clauses = [
                "part_number = ?",
                "quantity_at_site IS NOT NULL",
                "quantity_at_site > 0",
                "site_token != ''",
            ]
            params: list[object] = [part_number]
            if system:
                clauses.append("system = ?")
                params.append(system)
            rows = conn.execute(
                f"""
                WITH ranked AS (
                    SELECT
                        id,
                        part_number,
                        system,
                        site_token,
                        quantity_at_site,
                        source_path,
                        ROW_NUMBER() OVER (
                            PARTITION BY part_number, system, site_token
                            ORDER BY COALESCE(snapshot_year, 0) DESC,
                                     COALESCE(snapshot_date, '') DESC,
                                     id DESC
                        ) AS rn
                    FROM installed_base
                    WHERE {' AND '.join(clauses)}
                )
                SELECT id, part_number, system, site_token, quantity_at_site, source_path
                FROM ranked
                WHERE rn = 1
                """,
                params,
            ).fetchall()
            return rows
        finally:
            conn.close()

    def _stock_proxy_qty(self, part_number: str, system: str, site: str) -> tuple[int, float]:
        conn = self._open_optional_sqlite(self.po_db_path)
        if conn is None:
            return (0, 0.0)
        try:
            candidates = [
                (part_number, system, site),
                (part_number, system, ""),
                (part_number, "", ""),
            ]
            for cand_part, cand_system, cand_site in candidates:
                row = conn.execute(
                    """
                    SELECT SUM(COALESCE(qty, 0)), AVG(COALESCE(unit_price, 0))
                    FROM po_pricing
                    WHERE part_number = ? AND system = ? AND site_token = ?
                    """,
                    (cand_part, cand_system, cand_site),
                ).fetchone()
                qty = int(round(float(row[0] or 0.0))) if row else 0
                if qty > 0:
                    return qty, float(row[1] or 0.0)
            return (0, 0.0)
        finally:
            conn.close()

    def _parts_at_risk_rows(self, *, site: str, system: str, site_total: int) -> list[dict[str, Any]]:
        rows = self.store._conn.execute(
            """
            SELECT DISTINCT part_number
            FROM failure_events
            WHERE part_number != ''
              AND site_token = ?
              AND (? = '' OR system = ?)
            ORDER BY part_number ASC
            """,
            (site, system, system),
        ).fetchall()
        ranked_rows: list[dict[str, Any]] = []
        for row in rows:
            part_number = str(row[0] or "")
            history = self.store.monthly_failure_history(
                part_number,
                system=system or None,
                site_token=site or None,
                trailing_months=24,
            )
            months_history = int(history.get("span_months", 0) or 0)
            window_months = int(history.get("window_months", 0) or 0)
            if months_history < 12 or window_months <= 0:
                continue
            month_counts = [int(v) for v in (history.get("month_counts") or [])]
            total_failures = int(history.get("total_failures", 0) or 0)
            profile = self._load_po_part_profile(part_number)
            abc_tier = str(profile.get("abc_tier") or "UNKNOWN")
            service_level_z = float(_ABC_Z_VALUES.get(abc_tier, _SERVICE_LEVEL_Z))
            lead_time_days = int(profile.get("lead_time_days") or _DEFAULT_LEAD_TIME_DAYS)
            annualized_failures = total_failures * (12.0 / window_months)
            daily_demand_rate = (annualized_failures / float(site_total)) / 365.0
            normalized_month_counts = [count / float(site_total) for count in month_counts]
            monthly_sigma = float(statistics.stdev(normalized_month_counts)) if len(normalized_month_counts) >= 2 else 0.0
            safety_stock = service_level_z * monthly_sigma * math.sqrt(lead_time_days)
            reorder_point = (daily_demand_rate * lead_time_days) + safety_stock
            recommended_units = max(1, math.ceil(reorder_point))
            current_stock_proxy_qty, avg_unit_price = self._stock_proxy_qty(part_number, system, site)
            gap_units = recommended_units - current_stock_proxy_qty
            if gap_units <= 0:
                continue
            ranked_rows.append(
                {
                    "part_number": part_number,
                    "system": system,
                    "site_token": site,
                    "history_months": months_history,
                    "recommended_units": recommended_units,
                    "reorder_point": reorder_point,
                    "current_stock_proxy_qty": current_stock_proxy_qty,
                    "gap_units": gap_units,
                    "site_total_installed_qty": site_total,
                    "lead_time_days": lead_time_days,
                    "abc_tier": abc_tier,
                    "avg_unit_price": avg_unit_price,
                    "exposure_gap_cost": gap_units * avg_unit_price,
                }
            )
        ranked_rows.sort(
            key=lambda item: (-int(item["gap_units"]), -float(item["reorder_point"]), item["part_number"])
        )
        return ranked_rows[:10]

    def _substrate_footer(self, parsed: dict[str, Any]) -> str:
        cov = parsed.get("coverage", {})
        return (
            "\n---\n"
            "*Substrate coverage:*\n"
            f"- Total failure events: `{cov.get('total_events', 0):,}`\n"
            f"- Distinct parts: `{cov.get('distinct_parts', 0):,}`\n"
            f"- With system label: `{cov.get('with_system', 0):,}`\n"
            f"- With site label:   `{cov.get('with_site', 0):,}`\n"
            f"- With year label:   `{cov.get('with_year', 0):,}`\n"
            "\n*This answer was produced by deterministic SQL against the failure_events "
            "substrate. The LLM narrates the numbers but does not compute them.*"
        )

    def _cross_substrate_footer(self, parsed: dict[str, Any]) -> str:
        cov = parsed.get("coverage", {})
        return (
            "\n---\n"
            "*Cross-substrate coverage:*\n"
            f"- Failure events: `{cov.get('total_events', 0):,}`\n"
            f"- Distinct parts: `{cov.get('distinct_parts', 0):,}`\n"
            f"- po_pricing DB: `{self.po_db_path or '(missing)'}`\n"
            f"- installed_base DB: `{self.installed_base_db_path or '(missing)'}`\n"
            "\n*This answer was produced by deterministic SQL against failure_events, "
            "po_pricing, and installed_base substrates. The LLM narrates the numbers "
            "but does not compute them.*"
        )

    def _distinct_sites(self) -> list[str]:
        """Lightweight helper — return distinct non-empty site_token values."""
        try:
            rows = self.store._conn.execute(
                "SELECT DISTINCT site_token FROM failure_events "
                "WHERE site_token != ''"
            ).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []

    def _red(self, query: str, parsed: dict[str, Any], reason: str) -> AggregationResult:
        query_mode = str(parsed.get("query_mode") or "AGGREGATION").upper()
        heading = (
            "## Deterministic Inventory Recommendation — UNSUPPORTED"
            if query_mode == "INVENTORY"
            else "## Deterministic Aggregation — UNSUPPORTED"
        )
        text = (
            f"{heading}\n\n"
            f"**Query:** {query}\n\n"
            f"**Tier:** RED\n\n"
            f"**Reason:** {reason}\n\n"
            f"Substrate coverage: {parsed.get('coverage')}\n"
        )
        return AggregationResult(
            tier="RED",
            query=query,
            parsed_params=parsed,
            ranked_rows=[],
            per_year_rows={},
            evidence_by_part={},
            substrate_coverage=parsed.get("coverage") or {},
            context_text=text,
            sources=[],
            message=reason,
        )


# ---------------------------------------------------------------------------
# Unknown-reference detection (RED guard)
# ---------------------------------------------------------------------------

# Match "in X" / "for X" where X is the system name candidate.
_SYSTEM_MENTION_PAT = re.compile(
    r"\b(?:in|for|the)\s+(?:the\s+)?([A-Z]{3,}(?:[-_][A-Z0-9]+)?)"
    r"(?:\s+system)?\b"
)

# Match "at X" / "in X" / "for X" where X is a proper-name-looking site
# candidate. Accepts uppercase-start tokens (e.g., "Antarctica") and fully-
# uppercase tokens (e.g., "DJIBOUTI"). System-shaped tokens are filtered out
# by the caller using the known_systems set.
_SITE_MENTION_PAT = re.compile(
    r"\b(?:at|in|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b"
)


def _detect_unresolved_system_reference(
    query: str,
    resolved_system: str,
    known_canonicals: dict[str, list[str]],
    known_substrate_systems: set[str],
    known_parts: set[str] | None = None,
) -> str:
    """Return the unresolved system token if the query references a system-
    looking word that we couldn't resolve, else ''."""
    if resolved_system:
        return ""
    match = _SYSTEM_MENTION_PAT.search(query)
    if not match:
        return ""
    token = match.group(1).upper()
    # Skip if token is a year or known non-system acronym
    if re.fullmatch(r"(?:FY|CY)?\d{2,4}", token):
        return ""
    if token in (known_parts or set()):
        return ""
    known = {c.upper() for c in known_canonicals} | known_substrate_systems
    if token in known:
        return ""
    # Also skip if token happens to be a site alias (prevents "at GUAM" false-flag)
    return token


def _detect_unresolved_site_reference(
    query: str,
    resolved_site: str,
    known_site_aliases: dict[str, str],
    known_substrate_sites: set[str],
    known_systems: set[str] | None = None,
) -> str:
    """Return the unresolved site token if the query references an "at X" /
    "in X" / "for X" site-looking token that we couldn't resolve, else ''.

    Iterates over all matches in the query because a query like
    "top failing parts in monitoring system in Antarctica in 2024" has "in monitoring system" first
    (a system, not a site — must be skipped) and "in Antarctica" second
    (the actual unresolved-site hit we want to return).
    """
    if resolved_site:
        return ""
    known_systems = known_systems or set()
    # Common English stop-words that could be captured by the regex and
    # should NOT be treated as site references.
    _STOPWORDS = {
        "the", "this", "that", "these", "those", "our", "their", "my", "your",
        "every", "each", "last", "next", "past", "some", "any", "all",
        "all failing", "failing", "failed", "failure",
    }
    for match in _SITE_MENTION_PAT.finditer(query):
        token = match.group(1)
        token_lower = token.lower()
        token_upper = token.upper()
        # Skip if captured token is a known canonical system
        if token_upper in known_systems:
            continue
        # Skip stop-words that only look like proper nouns due to capitalization
        if token_lower in _STOPWORDS:
            continue
        # Resolved-canonical or substrate hit — skip
        canonical_form = token_lower.replace(" ", "_")
        if token_lower in known_site_aliases or canonical_form in known_site_aliases:
            continue
        if token_lower in known_substrate_sites:
            continue
        # Very short tokens are unlikely real site names (avoid false flag)
        if len(token) < 4:
            continue
        return token  # first unresolved site-looking hit, original casing
    return ""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _resolve_index_dir(data_dir_or_lance_path: str | Path) -> Path:
    p = Path(data_dir_or_lance_path)
    if p.name.lower() in {"lancedb", "lance_db", "lance"}:
        p = p.parent
    if p.name.lower() == "data" and not (p / "failure_events.sqlite3").exists():
        p = p / "index"
    if p.name.lower() != "index":
        p = p / "index"
    return p


def resolve_po_pricing_db_path(data_dir_or_lance_path: str | Path) -> Path:
    return _resolve_index_dir(data_dir_or_lance_path) / "po_pricing.sqlite3"


def resolve_installed_base_db_path(data_dir_or_lance_path: str | Path) -> Path:
    index_dir = _resolve_index_dir(data_dir_or_lance_path)
    candidates = [
        index_dir / "installed_base_end_to_end.sqlite3",
        index_dir / "installed_base.sqlite3",
        Path(r"C:\HybridRAG_V2_Dev2\data_isolated\installed_base_end_to_end.sqlite3"),
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size >= 1_000_000:
            return candidate
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]

def build_default_executor(
    data_dir: str | Path = "data",
    aliases_yaml: str | Path = "config/canonical_aliases.yaml",
) -> AggregationExecutor:
    """Build an executor against the default V2 substrate paths."""
    from src.store.failure_events_store import resolve_failure_events_db_path
    db_path = resolve_failure_events_db_path(data_dir)
    store = FailureEventsStore(db_path)
    aliases = AliasTables.load(aliases_yaml)
    return AggregationExecutor(
        store,
        aliases,
        po_db_path=resolve_po_pricing_db_path(data_dir),
        installed_base_db_path=resolve_installed_base_db_path(data_dir),
    )
