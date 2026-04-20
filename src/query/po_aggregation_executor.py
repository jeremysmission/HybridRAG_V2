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
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.store.failure_events_store import FailureEventsStore
from src.store.po_pricing_store import POPricingStore

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


def detect_aggregation_intent(query: str) -> bool:
    """Return True if query looks like failure-aggregation intent."""
    if not query:
        return False
    has_trigger = any(p.search(query) for p in _AGG_TRIGGERS)
    has_failure = bool(_FAILURE_AXIS.search(query))
    return has_trigger and has_failure


_PO_INTENT_TRIGGERS = (
    re.compile(r"\bhow\s+much\s+did\s+we\s+spend\b", re.IGNORECASE),
    re.compile(r"\bcost\s+of\b", re.IGNORECASE),
    re.compile(r"\breplacement\s+cost\b", re.IGNORECASE),
    re.compile(r"\blongest\s+lead\s+time\b", re.IGNORECASE),
    re.compile(r"\bmost\s+expensive\b", re.IGNORECASE),
    re.compile(r"\bmost\s+frequently\s+ordered\b", re.IGNORECASE),
    re.compile(r"\btop\s+ordered\b", re.IGNORECASE),
    re.compile(r"\btop\s+\d+.*\bordered\b", re.IGNORECASE),
    re.compile(r"\btop\s+(?:five|ten|three|seven).*\bordered\b", re.IGNORECASE),
    re.compile(r"\bordered\s+parts?\s+by\s+volume\b", re.IGNORECASE),
    re.compile(r"\bordered\s+most\s+often\b", re.IGNORECASE),
    re.compile(r"\btop\s+\d+\s+(?:parts?|items?).*?(?:cost|expensive)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+did\s+we\s+spend\b", re.IGNORECASE),
)

_PO_SPEND_SHAPE = re.compile(r"\b(how\s+much\s+did\s+we\s+spend|cost\s+of|spend\s+on)\b", re.IGNORECASE)
_PO_REPLACEMENT_SHAPE = re.compile(r"\breplacement\s+cost\b", re.IGNORECASE)
_PO_LEAD_SHAPE = re.compile(r"\b(longest\s+lead\s+time|lead\s+time)\b", re.IGNORECASE)
_PO_TOP_COST_SHAPE = re.compile(r"\b(most\s+expensive|top\s+\d+.*(?:cost|expensive)|highest\s+cost)\b", re.IGNORECASE)
_PO_TOP_VOLUME_SHAPE = re.compile(r"\b(by\s+volume|volume\s+ordered)\b", re.IGNORECASE)
_PO_TOP_ORDERED_SHAPE = re.compile(
    r"\b(most\s+frequently\s+ordered|top\s+ordered|top\s+.+\bordered|ordered\s+parts?|ordered\s+most\s+often)\b",
    re.IGNORECASE,
)
_QUERY_PART_PAT = re.compile(
    r"\b([A-Z0-9]{1,10}-[A-Z0-9-]{1,24}|[A-Z]{2,}[A-Z0-9]{2,})\b"
)
_HOSTILE_SQL_PATTERNS = (
    re.compile(r";"),
    re.compile(r"--"),
    re.compile(r"/\*"),
    re.compile(r"\b(drop|delete|truncate|alter|attach|detach|pragma|vacuum|insert|update)\b", re.IGNORECASE),
)


def detect_po_intent(query: str) -> bool:
    """Return True if query looks like deterministic PO spend / cost intent."""
    if not query:
        return False
    return any(pattern.search(query) for pattern in _PO_INTENT_TRIGGERS)


def parse_po_metric(query: str) -> str:
    if _PO_TOP_VOLUME_SHAPE.search(query or ""):
        return "top_volume"
    if _PO_REPLACEMENT_SHAPE.search(query or ""):
        return "replacement_cost"
    if _PO_LEAD_SHAPE.search(query or ""):
        return "longest_lead_time"
    if _PO_SPEND_SHAPE.search(query or ""):
        return "total_spend"
    if _PO_TOP_COST_SHAPE.search(query or ""):
        return "top_cost"
    if _PO_TOP_ORDERED_SHAPE.search(query or ""):
        return "top_ordered"
    return "top_cost"


def parse_query_part_number(query: str) -> str:
    raw = str(query or "").upper()
    for match in _QUERY_PART_PAT.finditer(raw):
        candidate = str(match.group(1) or "").strip().upper()
        if re.fullmatch(r"20\d{2}-20\d{2}", candidate):
            continue
        if re.fullmatch(r"(?:FY|CY)?20\d{2}", candidate):
            continue
        if re.fullmatch(r"\d{4,}", candidate):
            continue
        if candidate in {"PO", "COST", "SPEND", "ITEM", "ITEMS"}:
            continue
        if not re.search(r"\d", candidate):
            continue
        return candidate
    return ""


def parse_query_part_prefix(query: str) -> str:
    raw = str(query or "").upper()
    match = re.search(r"\b([A-Z]{2,}[A-Z0-9-]*)\s+FAMILY\b", raw)
    if not match:
        return ""
    candidate = str(match.group(1) or "").strip().upper()
    if re.fullmatch(r"20\d{2}", candidate):
        return ""
    return candidate


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
        po_store: POPricingStore | None = None,
    ):
        self.store = failure_store
        self.aliases = aliases
        self.po_store = po_store

    def try_execute(self, query: str) -> AggregationResult | None:
        """Return AggregationResult if query matches, else None (fall through to RAG).

        Fails closed when the canonical alias config is missing entirely —
        aggregation is a contract-bound feature, and without the canonical
        source of truth we refuse to run rather than silently substituting.
        """
        if detect_aggregation_intent(query):
            if not self.aliases.has_systems_configured():
                logger.warning(
                    "AggregationExecutor: canonical_aliases.yaml missing or empty — "
                    "failing closed (passthrough to RAG). Query: %s",
                    query,
                )
                return None
            return self.execute(query)
        if detect_po_intent(query):
            return self.execute_po(query)
        return None

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

    def execute_po(self, query: str) -> AggregationResult:
        top_n = parse_top_n(query)
        year_from, year_to = parse_year_range(query)
        resolved_system = self.aliases.resolve_system(query) if self.aliases else ""
        resolved_site = self.aliases.resolve_site(query) if self.aliases else ""
        system = resolved_system
        site = resolved_site
        metric = parse_po_metric(query)
        part_number = parse_query_part_number(query)
        part_prefix = parse_query_part_prefix(query)

        coverage = self.po_store.coverage_summary() if self.po_store else {}
        parsed = {
            "top_n": top_n,
            "year_from": year_from,
            "year_to": year_to,
            "system": system,
            "site_token": site,
            "metric": metric,
            "part_number": part_number,
            "part_prefix": part_prefix,
            "coverage": coverage,
        }

        if self.po_store is None:
            return self._red(query, parsed, "po_pricing substrate unavailable")
        if coverage.get("total_rows", 0) == 0:
            return self._red(query, parsed, "po_pricing substrate is empty — run scripts/populate_po_pricing.py")

        system = self._resolve_po_system_token(query, system)
        site = self._resolve_po_site_token(query, site)
        parsed["system"] = system
        parsed["site_token"] = site

        validation_error = self._validate_po_filters(
            query=query,
            resolved_system=resolved_system,
            resolved_site=resolved_site,
            normalized_system=system,
            normalized_site=site,
            part_number=part_number,
            year_from=year_from,
            year_to=year_to,
        )
        if validation_error:
            return self._red(query, parsed, validation_error)

        if metric == "replacement_cost":
            if not part_number:
                return self._red(query, parsed, "replacement-cost query requires a part number")
            summary = self.po_store.price_summary_for_part(
                part_number,
                system=system or None,
                site_token=site or None,
                year_from=year_from,
                year_to=year_to,
            )
            if summary.get("row_count", 0) <= 0:
                return self._red(query, parsed, "no PO pricing rows match the requested replacement-cost filters")
            evidence = {
                part_number: self.po_store.evidence_for_part(
                    part_number,
                    system=system or None,
                    site_token=site or None,
                    year_from=year_from,
                    year_to=year_to,
                    limit=3,
                )
            }
            text, sources = self._render_po_replacement_cost(query, summary, evidence, parsed)
            return AggregationResult(
                tier="GREEN",
                query=query,
                parsed_params=parsed,
                ranked_rows=[summary],
                per_year_rows={},
                evidence_by_part=evidence,
                substrate_coverage=coverage,
                context_text=text,
                sources=sources,
                message="",
            )

        if metric == "total_spend":
            if not part_number:
                return self._red(query, parsed, "PO spend query requires a part number")
            summary = self.po_store.total_spend_on_part(
                part_number,
                system=system or None,
                site_token=site or None,
                year_from=year_from,
                year_to=year_to,
            )
            if summary.get("row_count", 0) <= 0:
                return self._red(query, parsed, "no PO pricing rows match the requested spend filters")
            evidence = {
                part_number: self.po_store.evidence_for_part(
                    part_number,
                    system=system or None,
                    site_token=site or None,
                    year_from=year_from,
                    year_to=year_to,
                    limit=3,
                )
            }
            text, sources = self._render_po_spend(query, summary, evidence, parsed)
            return AggregationResult(
                tier="GREEN",
                query=query,
                parsed_params=parsed,
                ranked_rows=[summary],
                per_year_rows={},
                evidence_by_part=evidence,
                substrate_coverage=coverage,
                context_text=text,
                sources=sources,
                message="",
            )

        if metric == "top_ordered":
            rows = self.po_store.top_n_parts_by_order_count(
                limit=top_n,
                system=system or None,
                site_token=site or None,
                year_from=year_from,
                year_to=year_to,
                part_prefix=part_prefix or None,
            )
            if not rows:
                return self._red(query, parsed, "no PO pricing rows match the requested ordered-part filters")
            evidence = {
                row["part_number"]: self.po_store.evidence_for_part(
                    row["part_number"],
                    system=system or None,
                    site_token=site or None,
                    year_from=year_from,
                    year_to=year_to,
                    limit=2,
                )
                for row in rows
            }
            text, sources = self._render_po_top_ordered(query, rows, evidence, parsed)
            return AggregationResult(
                tier="GREEN",
                query=query,
                parsed_params=parsed,
                ranked_rows=rows,
                per_year_rows={},
                evidence_by_part=evidence,
                substrate_coverage=coverage,
                context_text=text,
                sources=sources,
                message="",
            )

        if metric == "top_volume":
            rows = self.po_store.top_n_parts_by_volume(
                limit=top_n,
                system=system or None,
                site_token=site or None,
                year_from=year_from,
                year_to=year_to,
                part_prefix=part_prefix or None,
            )
            if not rows:
                return self._red(query, parsed, "no PO pricing rows match the requested volume filters")
            evidence = {
                row["part_number"]: self.po_store.evidence_for_part(
                    row["part_number"],
                    system=system or None,
                    site_token=site or None,
                    year_from=year_from,
                    year_to=year_to,
                    limit=2,
                )
                for row in rows
            }
            text, sources = self._render_po_top_volume(query, rows, evidence, parsed)
            return AggregationResult(
                tier="GREEN",
                query=query,
                parsed_params=parsed,
                ranked_rows=rows,
                per_year_rows={},
                evidence_by_part=evidence,
                substrate_coverage=coverage,
                context_text=text,
                sources=sources,
                message="",
            )

        if metric == "longest_lead_time":
            rows = self.po_store.longest_lead_time_parts(
                limit=top_n,
                system=system or None,
                site_token=site or None,
                year_from=year_from,
                year_to=year_to,
                part_prefix=part_prefix or None,
            )
            if not rows:
                return self._red(query, parsed, "no PO lead-time rows match the requested filters")
            evidence = {
                row["part_number"]: self.po_store.evidence_for_part(
                    row["part_number"],
                    system=system or None,
                    site_token=site or None,
                    year_from=year_from,
                    year_to=year_to,
                    limit=2,
                )
                for row in rows
            }
            text, sources = self._render_po_lead_time(query, rows, evidence, parsed)
            return AggregationResult(
                tier="GREEN",
                query=query,
                parsed_params=parsed,
                ranked_rows=rows,
                per_year_rows={},
                evidence_by_part=evidence,
                substrate_coverage=coverage,
                context_text=text,
                sources=sources,
                message="",
            )

        rows = self.po_store.top_n_parts_by_cost(
            limit=top_n,
            system=system or None,
            site_token=site or None,
            year_from=year_from,
            year_to=year_to,
            part_prefix=part_prefix or None,
        )
        if not rows:
            return self._red(query, parsed, "no PO pricing rows match the requested cost filters")
        evidence = {
            row["part_number"]: self.po_store.evidence_for_part(
                row["part_number"],
                system=system or None,
                site_token=site or None,
                year_from=year_from,
                year_to=year_to,
                limit=2,
            )
            for row in rows
        }
        text, sources = self._render_po_top_cost(query, rows, evidence, parsed)
        return AggregationResult(
            tier="GREEN",
            query=query,
            parsed_params=parsed,
            ranked_rows=rows,
            per_year_rows={},
            evidence_by_part=evidence,
            substrate_coverage=coverage,
            context_text=text,
            sources=sources,
            message="",
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
            "| Rank | Part Number | Failure Count | Distinct Docs | First->Last Year |",
            "|------|-------------|---------------|---------------|-----------------|",
        ]
        sources: list[str] = []
        for i, r in enumerate(rows, 1):
            lines.append(
                f"| {i} | `{r['part_number']}` | {r['failure_count']} | "
                f"{r['distinct_docs']} | {r['first_year'] or '-'}->{r['last_year'] or '-'} |"
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

    def _render_po_top_cost(
        self,
        query: str,
        rows: list[dict],
        evidence: dict[str, list[dict]],
        parsed: dict[str, Any],
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic PO Cost Aggregation",
            "",
            f"**Query:** {query}",
            "**Confidence tier:** GREEN",
            "**Filters applied:**",
            f"- system: `{parsed.get('system') or 'any'}`",
            f"- site:   `{parsed.get('site_token') or 'any'}`",
            f"- years:  `{parsed.get('year_from')}–{parsed.get('year_to')}`"
            if parsed.get("year_from") else "- years:  `any`",
            f"- top N:  `{parsed.get('top_n')}`",
            "",
            "| Rank | Part Number | Total Cost | Avg Unit Price | Total Qty | Rows |",
            "|------|-------------|------------|----------------|-----------|------|",
        ]
        sources: list[str] = []
        for idx, row in enumerate(rows, start=1):
            lines.append(
                f"| {idx} | `{row['part_number']}` | ${row['total_cost']:,.2f} | "
                f"${row['avg_unit_price']:,.2f} | {row['total_qty']:.2f} | {row['row_count']} |"
            )
        lines.append("")
        lines.append("### Evidence")
        lines.append("")
        for row in rows:
            part = row["part_number"]
            lines.append(f"**{part}**")
            for ev in evidence.get(part, [])[:2]:
                if ev.get("source_path"):
                    sources.append(str(ev["source_path"]))
                lines.append(
                    f"- PO `{ev.get('po_number') or '-'}` | ${ev.get('unit_price', 0.0):,.2f} "
                    f"| qty={ev.get('qty', 0.0):.2f} | vendor={ev.get('vendor') or '-'} "
                    f"| date={ev.get('po_date') or '-'}"
                )
            lines.append("")
        lines.append(self._po_substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_po_top_ordered(
        self,
        query: str,
        rows: list[dict],
        evidence: dict[str, list[dict]],
        parsed: dict[str, Any],
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic PO Ordered-Parts Aggregation",
            "",
            f"**Query:** {query}",
            "**Confidence tier:** GREEN",
            "**Filters applied:**",
            f"- system: `{parsed.get('system') or 'any'}`",
            f"- site:   `{parsed.get('site_token') or 'any'}`",
            f"- years:  `{parsed.get('year_from')}–{parsed.get('year_to')}`"
            if parsed.get("year_from") else "- years:  `any`",
            f"- top N:  `{parsed.get('top_n')}`",
            "",
            "| Rank | Part Number | Order Count | Total Qty | Avg Unit Price | Total Cost |",
            "|------|-------------|-------------|-----------|----------------|------------|",
        ]
        sources: list[str] = []
        for idx, row in enumerate(rows, start=1):
            lines.append(
                f"| {idx} | `{row['part_number']}` | {row['row_count']} | "
                f"{row['total_qty']:.2f} | ${row['avg_unit_price']:,.2f} | ${row['total_cost']:,.2f} |"
            )
        lines.append("")
        lines.append("### Evidence")
        lines.append("")
        for row in rows:
            part = row["part_number"]
            lines.append(f"**{part}**")
            for ev in evidence.get(part, [])[:2]:
                if ev.get("source_path"):
                    sources.append(str(ev["source_path"]))
                lines.append(
                    f"- PO `{ev.get('po_number') or '-'}` | qty={ev.get('qty', 0.0):.2f} "
                    f"| ${ev.get('unit_price', 0.0):,.2f} | vendor={ev.get('vendor') or '-'} "
                    f"| date={ev.get('po_date') or '-'}"
                )
            lines.append("")
        lines.append(self._po_substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_po_top_volume(
        self,
        query: str,
        rows: list[dict],
        evidence: dict[str, list[dict]],
        parsed: dict[str, Any],
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic PO Volume Aggregation",
            "",
            f"**Query:** {query}",
            "**Confidence tier:** GREEN",
            "**Filters applied:**",
            f"- system: `{parsed.get('system') or 'any'}`",
            f"- site:   `{parsed.get('site_token') or 'any'}`",
            f"- years:  `{parsed.get('year_from')}–{parsed.get('year_to')}`"
            if parsed.get("year_from") else "- years:  `any`",
            f"- top N:  `{parsed.get('top_n')}`",
            "",
            "| Rank | Part Number | Total Qty | Order Count | Avg Unit Price | Total Cost |",
            "|------|-------------|-----------|-------------|----------------|------------|",
        ]
        sources: list[str] = []
        for idx, row in enumerate(rows, start=1):
            lines.append(
                f"| {idx} | `{row['part_number']}` | {row['total_qty']:.2f} | "
                f"{row['row_count']} | ${row['avg_unit_price']:,.2f} | ${row['total_cost']:,.2f} |"
            )
        lines.append("")
        lines.append("### Evidence")
        lines.append("")
        for row in rows:
            part = row["part_number"]
            lines.append(f"**{part}**")
            for ev in evidence.get(part, [])[:2]:
                if ev.get("source_path"):
                    sources.append(str(ev["source_path"]))
                lines.append(
                    f"- PO `{ev.get('po_number') or '-'}` | qty={ev.get('qty', 0.0):.2f} "
                    f"| ${ev.get('unit_price', 0.0):,.2f} | vendor={ev.get('vendor') or '-'} "
                    f"| date={ev.get('po_date') or '-'}"
                )
            lines.append("")
        lines.append(self._po_substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_po_spend(
        self,
        query: str,
        summary: dict[str, Any],
        evidence: dict[str, list[dict]],
        parsed: dict[str, Any],
    ) -> tuple[str, list[str]]:
        part = summary["part_number"]
        lines = [
            "## Deterministic PO Spend Aggregation",
            "",
            f"**Query:** {query}",
            "**Confidence tier:** GREEN",
            "",
            f"**Part number:** `{part}`",
            f"**Total spend:** `${summary['total_spend']:,.2f}`",
            f"**Total quantity:** `{summary['total_qty']:.2f}`",
            f"**Average unit price:** `${summary['avg_unit_price']:,.2f}`",
            f"**Price range:** `${summary['min_unit_price']:,.2f}` -> `${summary['max_unit_price']:,.2f}`",
            f"**Rows matched:** `{summary['row_count']}`",
            "",
            "### Evidence",
            "",
        ]
        sources: list[str] = []
        for ev in evidence.get(part, [])[:3]:
            if ev.get("source_path"):
                sources.append(str(ev["source_path"]))
            lines.append(
                f"- PO `{ev.get('po_number') or '-'}` | ${ev.get('unit_price', 0.0):,.2f} "
                f"| qty={ev.get('qty', 0.0):.2f} | vendor={ev.get('vendor') or '-'} "
                f"| date={ev.get('po_date') or '-'}"
            )
        lines.append("")
        lines.append(self._po_substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_po_replacement_cost(
        self,
        query: str,
        summary: dict[str, Any],
        evidence: dict[str, list[dict]],
        parsed: dict[str, Any],
    ) -> tuple[str, list[str]]:
        part = summary["part_number"]
        lines = [
            "## Deterministic PO Replacement-Cost Aggregation",
            "",
            f"**Query:** {query}",
            "**Confidence tier:** GREEN",
            "",
            f"**Part number:** `{part}`",
            f"**Latest observed price date:** `{summary['last_price_date'] or '-'}`",
            f"**Average unit price:** `${summary['avg_unit_price']:,.2f}`",
            f"**Maximum unit price:** `${summary['max_unit_price']:,.2f}`",
            f"**Minimum unit price:** `${summary['min_unit_price']:,.2f}`",
            f"**Rows matched:** `{summary['row_count']}`",
            "",
            "### Evidence",
            "",
        ]
        sources: list[str] = []
        for ev in evidence.get(part, [])[:3]:
            if ev.get("source_path"):
                sources.append(str(ev["source_path"]))
            lines.append(
                f"- PO `{ev.get('po_number') or '-'}` | ${ev.get('unit_price', 0.0):,.2f} "
                f"| qty={ev.get('qty', 0.0):.2f} | vendor={ev.get('vendor') or '-'} "
                f"| date={ev.get('po_date') or '-'}"
            )
        lines.append("")
        lines.append(self._po_substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _render_po_lead_time(
        self,
        query: str,
        rows: list[dict],
        evidence: dict[str, list[dict]],
        parsed: dict[str, Any],
    ) -> tuple[str, list[str]]:
        lines = [
            "## Deterministic PO Lead-Time Aggregation",
            "",
            f"**Query:** {query}",
            "**Confidence tier:** GREEN",
            "**Filters applied:**",
            f"- system: `{parsed.get('system') or 'any'}`",
            f"- site:   `{parsed.get('site_token') or 'any'}`",
            f"- years:  `{parsed.get('year_from')}–{parsed.get('year_to')}`"
            if parsed.get("year_from") else "- years:  `any`",
            f"- top N:  `{parsed.get('top_n')}`",
            "",
            "| Rank | Part Number | Max Lead Time (days) | Avg Lead Time (days) | Rows |",
            "|------|-------------|----------------------|----------------------|------|",
        ]
        sources: list[str] = []
        for idx, row in enumerate(rows, start=1):
            lines.append(
                f"| {idx} | `{row['part_number']}` | {row['max_lead_time_days']} | "
                f"{row['avg_lead_time_days']:.1f} | {row['row_count']} |"
            )
        lines.append("")
        lines.append("### Evidence")
        lines.append("")
        for row in rows:
            part = row["part_number"]
            lines.append(f"**{part}**")
            for ev in evidence.get(part, [])[:2]:
                if ev.get("source_path"):
                    sources.append(str(ev["source_path"]))
                lines.append(
                    f"- PO `{ev.get('po_number') or '-'}` | lead_time={ev.get('lead_time_days') or '-'} "
                    f"| vendor={ev.get('vendor') or '-'} | date={ev.get('po_date') or '-'}"
                )
            lines.append("")
        lines.append(self._po_substrate_footer(parsed))
        return "\n".join(lines), list(dict.fromkeys(sources))

    def _po_substrate_footer(self, parsed: dict[str, Any]) -> str:
        cov = parsed.get("coverage", {})
        return (
            "\n---\n"
            "*Substrate coverage:*\n"
            f"- Total pricing rows: `{cov.get('total_rows', 0):,}`\n"
            f"- With part number:   `{cov.get('with_part_number', 0):,}`\n"
            f"- With unit price:    `{cov.get('with_unit_price', 0):,}`\n"
            f"- With lead time:     `{cov.get('with_lead_time', 0):,}`\n"
            f"- Distinct parts:     `{cov.get('distinct_parts', 0):,}`\n"
            "\n*This answer was produced by deterministic SQL against the po_pricing "
            "substrate. The LLM narrates the numbers but does not compute them.*"
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

    def _resolve_po_system_token(self, query: str, system: str) -> str:
        if self.po_store is None:
            return system
        try:
            distinct_systems = self.po_store.distinct_systems()
        except Exception:
            distinct_systems = []
        if system:
            for candidate in distinct_systems:
                if str(candidate or "").upper() == system.upper():
                    return candidate
        q_lower = str(query or "").lower()
        for candidate in distinct_systems:
            text = str(candidate or "")
            if text and re.search(rf"\b{re.escape(text.lower())}\b", q_lower):
                return text
        return system

    def _resolve_po_site_token(self, query: str, site: str) -> str:
        if self.po_store is None:
            return site
        try:
            distinct_sites = self.po_store.distinct_sites()
        except Exception:
            distinct_sites = []
        if not distinct_sites:
            return site

        lowered_sites = {str(candidate or "").lower(): str(candidate or "") for candidate in distinct_sites}
        if site:
            direct = lowered_sites.get(site.lower())
            if direct:
                return direct
            normalized = lowered_sites.get(site.replace("_", " ").lower())
            if normalized:
                return normalized
            if self.aliases:
                for candidate in distinct_sites:
                    candidate_text = str(candidate or "")
                    if candidate_text and self.aliases.resolve_site(candidate_text) == site:
                        return candidate_text

        q_lower = str(query or "").lower()
        for candidate in distinct_sites:
            candidate_text = str(candidate or "")
            if candidate_text and re.search(rf"\b{re.escape(candidate_text.lower())}\b", q_lower):
                return candidate_text
        return site

    def _validate_po_filters(
        self,
        *,
        query: str,
        resolved_system: str,
        resolved_site: str,
        normalized_system: str,
        normalized_site: str,
        part_number: str,
        year_from: int | None,
        year_to: int | None,
    ) -> str:
        hostile_reason = _detect_hostile_query_text(query)
        if hostile_reason:
            return hostile_reason

        po_systems = {s.upper() for s in self._po_distinct_systems() if s}
        unresolved_system = _detect_unresolved_system_reference(
            query,
            resolved_system or normalized_system,
            self.aliases.system_to_aliases if self.aliases else {},
            po_systems,
        )
        if unresolved_system:
            return (
                f"query references unknown system '{unresolved_system}' — "
                f"not present in canonical_aliases.yaml or po_pricing substrate"
            )

        unresolved_site = _detect_unresolved_site_reference(
            query,
            resolved_site or normalized_site,
            self.aliases.site_alias_lookup if self.aliases else {},
            {s.lower() for s in self._po_distinct_sites() if s},
            known_systems=({c.upper() for c in self.aliases.system_to_aliases} if self.aliases else set()) | po_systems,
        )
        if unresolved_site:
            return (
                f"query references unknown site '{unresolved_site}' — "
                f"not present in canonical_aliases.yaml or po_pricing substrate"
            )

        year_error = self._validate_po_year_range(year_from=year_from, year_to=year_to)
        if year_error:
            return year_error

        if part_number and not self._po_part_exists(part_number):
            return (
                f"part number '{part_number}' is not present in the po_pricing substrate"
            )

        return ""

    def _validate_po_year_range(self, *, year_from: int | None, year_to: int | None) -> str:
        if year_from is None and year_to is None:
            return ""
        min_year, max_year = self._po_year_bounds()
        if min_year is None or max_year is None:
            return ""
        requested_from = year_from if year_from is not None else min_year
        requested_to = year_to if year_to is not None else max_year
        if requested_to < min_year or requested_from > max_year:
            return (
                f"requested year range {requested_from}-{requested_to} is outside "
                f"po_pricing coverage {min_year}-{max_year}"
            )
        return ""

    def _po_year_bounds(self) -> tuple[int | None, int | None]:
        if self.po_store is None:
            return (None, None)
        try:
            row = self.po_store._conn.execute(
                """
                SELECT
                    MIN(CAST(substr(po_date, 1, 4) AS INTEGER)),
                    MAX(CAST(substr(po_date, 1, 4) AS INTEGER))
                FROM po_pricing
                WHERE po_date IS NOT NULL
                  AND TRIM(po_date) != ''
                """
            ).fetchone()
        except Exception:
            return (None, None)
        if not row:
            return (None, None)
        min_year, max_year = row
        return (
            int(min_year) if min_year is not None else None,
            int(max_year) if max_year is not None else None,
        )

    def _po_part_exists(self, part_number: str) -> bool:
        if self.po_store is None or not part_number:
            return False
        try:
            row = self.po_store._conn.execute(
                "SELECT 1 FROM po_pricing WHERE part_number = ? LIMIT 1",
                (str(part_number or "").strip().upper(),),
            ).fetchone()
        except Exception:
            return False
        return bool(row)

    def _po_distinct_systems(self) -> list[str]:
        if self.po_store is None:
            return []
        try:
            return self.po_store.distinct_systems()
        except Exception:
            return []

    def _po_distinct_sites(self) -> list[str]:
        if self.po_store is None:
            return []
        try:
            return self.po_store.distinct_sites()
        except Exception:
            return []

    def _red(self, query: str, parsed: dict[str, Any], reason: str) -> AggregationResult:
        text = (
            "## Deterministic Aggregation — UNSUPPORTED\n\n"
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
    if re.search(r"[\d-]", token):
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
    "top failing parts in NEXION in Antarctica in 2024" has "in NEXION" first
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


def _detect_hostile_query_text(query: str) -> str:
    text = str(query or "")
    for pattern in _HOSTILE_SQL_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        token = str(match.group(0) or "").strip()
        return (
            f"query contains hostile or non-analytical SQL text '{token}' — "
            f"refusing deterministic execution"
        )
    return ""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_default_executor(
    data_dir: str | Path = "data",
    aliases_yaml: str | Path = "config/canonical_aliases.yaml",
) -> AggregationExecutor:
    """Build an executor against the default V2 substrate paths."""
    from src.store.failure_events_store import resolve_failure_events_db_path
    from src.store.po_pricing_store import resolve_po_pricing_db_path
    db_path = resolve_failure_events_db_path(data_dir)
    po_db_path = resolve_po_pricing_db_path(data_dir)
    store = FailureEventsStore(db_path)
    po_store = POPricingStore(po_db_path)
    aliases = AliasTables.load(aliases_yaml)
    return AggregationExecutor(store, aliases, po_store=po_store)
