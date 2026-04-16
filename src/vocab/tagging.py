"""Deterministic tagging helpers built on shipped controlled vocabulary packs.

This is intentionally a low-risk consumer:
- read-only relative to extraction defaults
- exact/bounded alias matching only
- ambiguity is surfaced, not auto-resolved away
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.vocab.pack_loader import VocabEntry, VocabPack, load_all_packs
from src.vocab.pack_reports import ScanHit, find_scan_hits


@dataclass(frozen=True)
class AmbiguousAliasWarning:
    """One ambiguous alias span found during deterministic tagging."""

    alias: str
    matched_text: str
    start: int
    end: int
    candidate_count: int
    candidates: tuple[dict[str, str], ...]


def _build_entry_index(packs: Iterable[VocabPack]) -> dict[tuple[str, str], VocabEntry]:
    """Assemble the structured object this workflow needs for its next step."""
    out: dict[tuple[str, str], VocabEntry] = {}
    for pack in packs:
        for entry in pack.entries:
            out[(pack.pack_id, entry.term_id)] = entry
    return out


def _doc_family_rules(domain_counts: Counter[str], kind_counts: Counter[str]) -> list[str]:
    """Support the tagging workflow by handling the doc family rules step."""
    tags: list[str] = []
    if kind_counts.get("form", 0):
        tags.append("government_form_document")
    if kind_counts.get("location", 0):
        tags.append("site_document")
    if domain_counts.get("cyber", 0):
        tags.append("cyber_document")
    if domain_counts.get("pmi_evm", 0):
        tags.append("program_management_document")
    return tags


def build_tagging_result(
    directory: str | Path,
    text: str,
) -> dict[str, Any]:
    """Scan text and return deterministic vocab tags + ambiguity warnings."""
    packs = load_all_packs(directory)
    entry_index = _build_entry_index(packs)
    pack_by_id = {pack.pack_id: pack for pack in packs}
    hits = find_scan_hits(packs, text)

    domain_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    unique_terms: dict[tuple[str, str], dict[str, Any]] = {}
    form_family: list[dict[str, Any]] = []
    site_family: list[dict[str, Any]] = []

    for hit in hits:
        pack = pack_by_id[hit.pack_id]
        entry = entry_index[(hit.pack_id, hit.term_id)]
        domain_counts[pack.domain] += 1
        kind_counts[hit.kind] += 1
        unique_terms.setdefault(
            (hit.pack_id, hit.term_id),
            {
                "pack_id": hit.pack_id,
                "pack_name": hit.pack_name,
                "term_id": hit.term_id,
                "canonical": hit.canonical,
                "domain": pack.domain,
                "kind": hit.kind,
                "category": hit.category,
                "collision_risk": hit.collision_risk,
                "regex_safe": hit.regex_safe,
                "retrieval_expand": hit.retrieval_expand,
            },
        )
        if hit.kind == "form":
            form_family.append(
                {
                    "canonical": hit.canonical,
                    "term_id": hit.term_id,
                    "matched_text": hit.matched_text,
                    "form_number": entry.extras.get("form_number", hit.canonical),
                    "form_title": entry.extras.get("form_title", ""),
                }
            )
        elif hit.kind == "location":
            site_family.append(
                {
                    "canonical": hit.canonical,
                    "term_id": hit.term_id,
                    "matched_text": hit.matched_text,
                    "service": entry.extras.get("service", ""),
                    "type": entry.extras.get("type", ""),
                }
            )

    ambiguous_groups: dict[tuple[str, int, int], list[ScanHit]] = defaultdict(list)
    for hit in hits:
        if hit.ambiguous:
            ambiguous_groups[(hit.normalized_alias, hit.start, hit.end)].append(hit)

    warnings: list[AmbiguousAliasWarning] = []
    for (alias, start, end), group in sorted(ambiguous_groups.items(), key=lambda item: (item[0][1], item[0][2], item[0][0])):
        matched_text = group[0].matched_text
        candidates = tuple(
            {
                "pack_id": hit.pack_id,
                "term_id": hit.term_id,
                "canonical": hit.canonical,
                "kind": hit.kind,
                "category": hit.category,
            }
            for hit in sorted(group, key=lambda item: (item.pack_id, item.term_id))
        )
        warnings.append(
            AmbiguousAliasWarning(
                alias=alias,
                matched_text=matched_text,
                start=start,
                end=end,
                candidate_count=len(candidates),
                candidates=candidates,
            )
        )

    dedup_form_family = list({item["term_id"]: item for item in form_family}.values())
    dedup_site_family = list({item["term_id"]: item for item in site_family}.values())

    return {
        "input_length": len(text or ""),
        "hit_count": len(hits),
        "doc_family": _doc_family_rules(domain_counts, kind_counts),
        "form_family": dedup_form_family,
        "site_family": dedup_site_family,
        "vocab_domain_hits": {
            domain: {
                "hit_count": count,
                "unique_term_count": sum(1 for item in unique_terms.values() if item["domain"] == domain),
            }
            for domain, count in sorted(domain_counts.items())
        },
        "ambiguous_alias_warnings": [warning.__dict__ for warning in warnings],
        "matched_terms": list(unique_terms.values()),
        "scan_hits": [hit.__dict__ for hit in hits],
    }


def format_tagging_result(result: dict[str, Any]) -> str:
    """Render a compact human-readable tagging summary."""
    lines: list[str] = []
    lines.append("Deterministic Vocab Tags")
    lines.append(f"Input length: {result['input_length']}")
    lines.append(f"Scan hits: {result['hit_count']}")

    doc_family = result.get("doc_family") or []
    lines.append(
        "Doc family: " + (", ".join(doc_family) if doc_family else "none")
    )

    if result.get("form_family"):
        lines.append("Form family:")
        for item in result["form_family"]:
            title = f" - {item['form_title']}" if item.get("form_title") else ""
            lines.append(
                f"  - {item['canonical']} ({item['matched_text']}){title}"
            )

    if result.get("site_family"):
        lines.append("Site family:")
        for item in result["site_family"]:
            suffix = ""
            if item.get("service") or item.get("type"):
                suffix = f" [{item.get('service', '')} {item.get('type', '')}]".rstrip()
            lines.append(f"  - {item['canonical']} ({item['matched_text']}){suffix}")

    domain_hits = result.get("vocab_domain_hits") or {}
    if domain_hits:
        lines.append("Vocab domain hits:")
        for domain, info in domain_hits.items():
            lines.append(
                f"  - {domain}: hits={info['hit_count']} unique_terms={info['unique_term_count']}"
            )

    warnings = result.get("ambiguous_alias_warnings") or []
    lines.append(f"Ambiguous alias warnings: {len(warnings)}")
    for warning in warnings:
        candidates = ", ".join(
            f"{item['pack_id']}/{item['term_id']}" for item in warning["candidates"]
        )
        lines.append(
            f"  - [{warning['start']}:{warning['end']}] {warning['matched_text']} "
            f"=> {candidates}"
        )

    matched_terms = result.get("matched_terms") or []
    if matched_terms:
        lines.append("Matched terms:")
        for item in matched_terms:
            lines.append(
                f"  - {item['pack_id']}/{item['term_id']} {item['canonical']} "
                f"[{item['domain']}, {item['kind']}, collision={item['collision_risk']}]"
            )

    return "\n".join(lines)
