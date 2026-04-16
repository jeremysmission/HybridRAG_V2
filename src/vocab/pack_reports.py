"""Read-only reporting helpers for controlled vocabulary packs.

This module is intentionally narrow: it validates, summarizes, and
looks up terms without changing extraction behavior or promotion rules.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable

import yaml

from src.vocab.pack_loader import VocabEntry, VocabPack, VocabPackError, load_all_packs, validate_pack_dict


@dataclass(frozen=True)
class LookupHit:
    """A single normalized lookup hit across loaded packs."""

    pack_id: str
    pack_name: str
    term_id: str
    canonical: str
    matched_text: str
    kind: str
    category: str
    regex_safe: bool
    retrieval_expand: bool
    collision_risk: str
    source_kind: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ScanHit:
    """A deterministic in-text hit for a controlled-vocabulary alias."""

    pack_id: str
    pack_name: str
    term_id: str
    canonical: str
    matched_text: str
    normalized_alias: str
    kind: str
    category: str
    start: int
    end: int
    regex_safe: bool
    retrieval_expand: bool
    collision_risk: str
    source_kind: str
    ambiguous: bool
    aliases: tuple[str, ...]


def _entry_matches(entry: VocabEntry, query: str) -> bool:
    """Support the pack reports workflow by handling the entry matches step."""
    needle = query.strip().lower()
    if not needle:
        return False
    return needle in entry.alias_set


def _build_alias_index(
    packs: Iterable[VocabPack],
) -> dict[str, list[tuple[VocabPack, VocabEntry]]]:
    """Assemble the structured object this workflow needs for its next step."""
    alias_index: dict[str, list[tuple[VocabPack, VocabEntry]]] = defaultdict(list)
    for pack in packs:
        for entry in pack.entries:
            for alias in entry.alias_set:
                alias_index[alias].append((pack, entry))
    return dict(alias_index)


def _is_boundary_char(ch: str) -> bool:
    """Support the pack reports workflow by handling the is boundary char step."""
    return not (ch.isalnum() or ch == "_")


def _is_bounded_match(text: str, start: int, end: int) -> bool:
    """Support the pack reports workflow by handling the is bounded match step."""
    left_ok = start == 0 or _is_boundary_char(text[start - 1])
    right_ok = end == len(text) or _is_boundary_char(text[end])
    return left_ok and right_ok


def build_cross_pack_alias_collisions(
    packs: Iterable[VocabPack],
) -> dict[str, list[dict[str, str]]]:
    """Return aliases that resolve to more than one entry across loaded packs."""
    collisions: dict[str, list[dict[str, str]]] = {}
    for alias, refs in _build_alias_index(packs).items():
        unique_refs = {
            (pack.pack_id, pack.pack_name, entry.term_id, entry.canonical)
            for pack, entry in refs
        }
        if len(unique_refs) <= 1:
            continue
        collisions[alias] = [
            {
                "pack_id": pack_id,
                "pack_name": pack_name,
                "term_id": term_id,
                "canonical": canonical,
            }
            for pack_id, pack_name, term_id, canonical in sorted(unique_refs)
        ]
    return dict(sorted(collisions.items()))


def find_lookup_hits(packs: Iterable[VocabPack], query: str) -> list[LookupHit]:
    """Return every entry in every pack that matches ``query`` by alias or canonical."""
    needle = (query or "").strip().lower()
    if not needle:
        return []

    hits: list[LookupHit] = []
    for pack in packs:
        for entry in pack.entries:
            if not _entry_matches(entry, needle):
                continue
            hits.append(
                LookupHit(
                    pack_id=pack.pack_id,
                    pack_name=pack.pack_name,
                    term_id=entry.term_id,
                    canonical=entry.canonical,
                    matched_text=query,
                    kind=entry.kind,
                    category=entry.category,
                    regex_safe=entry.regex_safe,
                    retrieval_expand=entry.retrieval_expand,
                    collision_risk=entry.collision_risk,
                    source_kind=entry.source_kind,
                    aliases=tuple(entry.aliases),
                )
            )
    return hits


def find_scan_hits(packs: Iterable[VocabPack], text: str) -> list[ScanHit]:
    """Return deterministic alias hits found inside ``text``.

    Matching is literal and case-insensitive. Hits are accepted only when
    they are bounded by non-word characters (or string edges) so short terms
    like ``CPI`` do not fire inside longer tokens like ``CPIX``.

    Overlapping candidates are resolved longest-match-first at the same
    position, then one span is kept. If the winning alias maps to multiple
    entries across packs, one hit is emitted per entry with ``ambiguous=True``.
    """
    haystack = text or ""
    if not haystack.strip():
        return []

    alias_index = _build_alias_index(packs)
    span_candidates: list[tuple[int, int, str, str, list[tuple[VocabPack, VocabEntry]]]] = []

    for alias, refs in alias_index.items():
        pattern = re.compile(re.escape(alias), flags=re.IGNORECASE)
        for match in pattern.finditer(haystack):
            start, end = match.span()
            if not _is_bounded_match(haystack, start, end):
                continue
            span_candidates.append((start, end, alias, match.group(0), refs))

    span_candidates.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))

    accepted_spans: list[tuple[int, int]] = []
    scan_hits: list[ScanHit] = []
    for start, end, alias, matched_text, refs in span_candidates:
        if any(not (end <= s or start >= e) for s, e in accepted_spans):
            continue
        accepted_spans.append((start, end))
        ambiguous = len(
            {(pack.pack_id, entry.term_id) for pack, entry in refs}
        ) > 1
        for pack, entry in refs:
            scan_hits.append(
                ScanHit(
                    pack_id=pack.pack_id,
                    pack_name=pack.pack_name,
                    term_id=entry.term_id,
                    canonical=entry.canonical,
                    matched_text=matched_text,
                    normalized_alias=alias,
                    kind=entry.kind,
                    category=entry.category,
                    start=start,
                    end=end,
                    regex_safe=entry.regex_safe,
                    retrieval_expand=entry.retrieval_expand,
                    collision_risk=entry.collision_risk,
                    source_kind=entry.source_kind,
                    ambiguous=ambiguous,
                    aliases=tuple(entry.aliases),
                )
            )

    return sorted(scan_hits, key=lambda hit: (hit.start, hit.end, hit.pack_id, hit.term_id))


def summarize_pack(pack: VocabPack) -> dict[str, Any]:
    """Produce a compact summary for one pack."""
    kind_counts = Counter(entry.kind for entry in pack.entries)
    collision_counts = Counter(entry.collision_risk for entry in pack.entries)
    source_counts = Counter(entry.source_kind for entry in pack.entries)
    regex_safe_count = sum(1 for entry in pack.entries if entry.regex_safe)
    retrieval_expand_count = sum(1 for entry in pack.entries if entry.retrieval_expand)
    alias_count = sum(len(entry.aliases) for entry in pack.entries)

    return {
        "pack_id": pack.pack_id,
        "pack_name": pack.pack_name,
        "domain": pack.domain,
        "release_tier": pack.release_tier,
        "status": pack.status,
        "entry_count": len(pack.entries),
        "kind_counts": dict(sorted(kind_counts.items())),
        "collision_counts": dict(sorted(collision_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "regex_safe_count": regex_safe_count,
        "retrieval_expand_count": retrieval_expand_count,
        "alias_count": alias_count,
        "has_local_only_sources": bool(pack.provenance.get("local_only_sources")),
    }


def build_vocab_report(
    directory: str | Path,
    lookups: Iterable[str] | None = None,
    scan_text: str | None = None,
) -> dict[str, Any]:
    """Validate and summarize all packs in ``directory``.

    Raises :class:`VocabPackError` if a pack fails to load or validate.
    """
    root = Path(directory)
    packs = load_all_packs(root)

    validation: dict[str, list[str]] = {}
    for pack_file in sorted(root.glob("*.yaml")):
        raw = yaml.safe_load(pack_file.read_text(encoding="utf-8"))
        validation[pack_file.name] = validate_pack_dict(raw)

    all_entries = sum(len(pack.entries) for pack in packs)
    all_aliases = sum(len(entry.aliases) for pack in packs for entry in pack.entries)
    all_regex_safe = sum(1 for pack in packs for entry in pack.entries if entry.regex_safe)
    all_retrieval_expand = sum(
        1 for pack in packs for entry in pack.entries if entry.retrieval_expand
    )
    kind_counts = Counter(entry.kind for pack in packs for entry in pack.entries)
    collision_counts = Counter(
        entry.collision_risk for pack in packs for entry in pack.entries
    )
    source_counts = Counter(entry.source_kind for pack in packs for entry in pack.entries)
    collisions = build_cross_pack_alias_collisions(packs)

    report: dict[str, Any] = {
        "directory": str(root),
        "pack_count": len(packs),
        "entry_count": all_entries,
        "alias_count": all_aliases,
        "regex_safe_count": all_regex_safe,
        "retrieval_expand_count": all_retrieval_expand,
        "kind_counts": dict(sorted(kind_counts.items())),
        "collision_counts": dict(sorted(collision_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "cross_pack_alias_collisions": collisions,
        "packs": [summarize_pack(pack) for pack in packs],
        "validation": validation,
        "lookup_hits": [],
        "lookup_summary": {},
        "text_scan_hits": [],
        "text_scan_summary": {},
    }

    if lookups:
        grouped_hits: dict[str, list[LookupHit]] = defaultdict(list)
        for lookup in lookups:
            grouped_hits[lookup] = find_lookup_hits(packs, lookup)
        report["lookup_hits"] = {
            lookup: [hit.__dict__ for hit in hits]
            for lookup, hits in grouped_hits.items()
        }
        report["lookup_summary"] = {
            lookup: {
                "hit_count": len(hits),
                "ambiguous": len({hit.term_id for hit in hits}) > 1,
            }
            for lookup, hits in grouped_hits.items()
        }

    if scan_text is not None:
        scan_hits = find_scan_hits(packs, scan_text)
        report["text_scan_hits"] = [hit.__dict__ for hit in scan_hits]
        report["text_scan_summary"] = {
            "input_length": len(scan_text),
            "hit_count": len(scan_hits),
            "ambiguous_hit_count": sum(1 for hit in scan_hits if hit.ambiguous),
            "matched_pack_ids": sorted({hit.pack_id for hit in scan_hits}),
        }

    return report


def format_vocab_report(report: dict[str, Any]) -> str:
    """Render the report as a concise human-readable text block."""
    lines: list[str] = []
    lines.append("Vocabulary Pack Report")
    lines.append(f"Directory: {report['directory']}")
    lines.append(f"Packs: {report['pack_count']}")
    lines.append(f"Entries: {report['entry_count']}")
    lines.append(f"Aliases: {report['alias_count']}")
    lines.append(
        f"Regex safe: {report['regex_safe_count']}  "
        f"Retrieval expand: {report['retrieval_expand_count']}"
    )

    if report.get("kind_counts"):
        lines.append("Kinds:")
        for kind, count in report["kind_counts"].items():
            lines.append(f"  - {kind}: {count}")

    if report.get("collision_counts"):
        lines.append("Collision risk:")
        for risk, count in report["collision_counts"].items():
            lines.append(f"  - {risk}: {count}")

    if report.get("source_counts"):
        lines.append("Source kinds:")
        for kind, count in report["source_counts"].items():
            lines.append(f"  - {kind}: {count}")

    collisions = report.get("cross_pack_alias_collisions") or {}
    lines.append(f"Cross-pack alias collisions: {len(collisions)}")
    for alias, refs in list(collisions.items())[:10]:
        targets = ", ".join(f"{ref['pack_id']}/{ref['term_id']}" for ref in refs)
        lines.append(f"  - {alias}: {targets}")

    lines.append("Packs:")
    for pack in report.get("packs", []):
        lines.append(
            f"  - {pack['pack_id']} ({pack['release_tier']}, {pack['entry_count']} entries)"
        )
        lines.append(
            f"    regex_safe={pack['regex_safe_count']} "
            f"retrieval_expand={pack['retrieval_expand_count']} "
            f"aliases={pack['alias_count']}"
        )
        if pack["kind_counts"]:
            kind_text = ", ".join(f"{k}:{v}" for k, v in pack["kind_counts"].items())
            lines.append(f"    kinds={kind_text}")

    lookup_summary = report.get("lookup_summary") or {}
    if lookup_summary:
        lines.append("Lookups:")
        for lookup, summary in lookup_summary.items():
            lines.append(
                f"  - {lookup}: hits={summary['hit_count']} "
                f"ambiguous={str(summary['ambiguous']).lower()}"
            )
            for hit in report["lookup_hits"].get(lookup, []):
                lines.append(
                    f"    -> {hit['pack_id']}/{hit['term_id']} "
                    f"{hit['canonical']} [{hit['kind']}, collision={hit['collision_risk']}, "
                    f"regex_safe={str(hit['regex_safe']).lower()}]"
                )

    text_scan_summary = report.get("text_scan_summary") or {}
    if text_scan_summary:
        lines.append("Text scan:")
        lines.append(
            f"  - input_length={text_scan_summary['input_length']} "
            f"hits={text_scan_summary['hit_count']} "
            f"ambiguous_hits={text_scan_summary['ambiguous_hit_count']}"
        )
        for hit in report.get("text_scan_hits", []):
            lines.append(
                f"    -> [{hit['start']}:{hit['end']}] {hit['matched_text']} => "
                f"{hit['pack_id']}/{hit['term_id']} {hit['canonical']} "
                f"(ambiguous={str(hit['ambiguous']).lower()})"
            )

    validation = report.get("validation") or {}
    if validation:
        line_count = sum(len(errors) for errors in validation.values())
        lines.append(f"Validation errors: {line_count}")

    return "\n".join(lines)
