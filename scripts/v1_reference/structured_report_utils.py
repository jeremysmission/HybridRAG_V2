"""Deterministic helpers for structured report extraction and routing."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


_HEADER_LABEL_RE = re.compile(
    r"^\s*(?P<label>[A-Za-z][A-Za-z0-9 /#&()_-]{1,40}):\s*(?P<value>.*)$",
    re.MULTILINE,
)
_REPORT_ID_RE = re.compile(r"\b(?:FSR|UMR|IR|ASV|RTS)-[A-Za-z0-9_-]+\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_YEAR_RANGE_RE = re.compile(
    r"\b(?:from\s+)?((?:19|20)\d{2})\s*(?:-|to|through|thru)\s*((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_SECTION_STOP_RE = re.compile(
    r"^(?:"
    r"[A-Z][A-Z0-9 /#&()_-]{2,}:"
    r"|[A-Z][A-Z0-9 /#&()_-]{4,}$"
    r"|={4,}"
    r"|[-]{4,}"
    r"|\d+\.\s+"
    r")"
)
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'/-]*")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d(). -]{6,}\d)")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

_REPORT_LABELS = ("report",)
_DATE_LABELS = ("date",)
_SITE_LABELS = ("site", "location")
_SYSTEM_LABELS = ("system", "affected system")
_VISIT_TYPE_LABELS = ("visit type", "visit", "maintenance type")
_PRIORITY_LABELS = ("priority",)
_CATEGORY_LABELS = ("category",)
_REPORTED_BY_LABELS = ("reported by", "technician", "engineer", "signed")
_FOLLOW_ON_LABELS = ("follow-on actions", "follow on actions", "follow-up actions")
_CORRECTIVE_ACTION_LABELS = ("corrective action", "corrective action verified")
_REPAIR_SUMMARY_LABELS = ("repair summary", "resolution", "repair/fix information")
_POC_LABELS = ("point of contact", "poc", "contact")

_US_REGION_TOKENS = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
    "district of columbia",
    "usa",
    "u.s.a",
    "u.s.",
    "united states",
    "united states of america",
}

_COUNTRY_ALIASES = {
    "guam": "Guam",
    "japan": "Japan",
    "korea": "Korea",
    "south korea": "Korea",
    "north korea": "North Korea",
    "australia": "Australia",
    "new zealand": "New Zealand",
    "ascension island": "Ascension Island",
    "antarctica": "Antarctica",
    "iceland": "Iceland",
    "canada": "Canada",
    "philippines": "Philippines",
    "india": "India",
    "brazil": "Brazil",
    "peru": "Peru",
    "chile": "Chile",
    "greenland": "Greenland",
    "norway": "Norway",
    "sweden": "Sweden",
    "finland": "Finland",
}

_ACTION_SYNONYMS = (
    ("replaced", ("replace", "replaced", "swap", "swapped", "replacement")),
    ("installed", ("install", "installed", "installation")),
    ("removed", ("remove", "removed", "uninstalled")),
    ("repaired", ("repair", "repaired", "fixed", "restored")),
    ("inspected", ("inspect", "inspected", "checked", "tested", "verified")),
    ("adjusted", ("adjust", "adjusted", "aligned", "calibrated", "tuned")),
    ("upgraded", ("upgrade", "upgraded", "updated")),
)


def normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace into a single readable space."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_for_match(value: str) -> str:
    """Normalize free text for simple case-insensitive contains checks."""
    lowered = str(value or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def titleize_preserving_tokens(value: str) -> str:
    """Return a readable title-cased string without mangling acronyms/IDs."""
    parts = normalize_whitespace(value).split()
    rendered: list[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if any(ch.isdigit() for ch in token) or token.isupper():
            rendered.append(token)
            continue
        if "-" in token:
            rendered.append("-".join(titleize_preserving_tokens(piece) for piece in token.split("-")))
            continue
        rendered.append(token[:1].upper() + token[1:].lower())
    return " ".join(rendered)


def extract_header_map(text: str) -> dict[str, str]:
    """Return normalized header labels mapped to their first observed value."""
    mapping: dict[str, str] = {}
    for match in _HEADER_LABEL_RE.finditer(str(text or "")):
        label = normalize_for_match(match.group("label"))
        if label and label not in mapping:
            mapping[label] = normalize_whitespace(match.group("value"))
    return mapping


def extract_header_value(text: str, labels: Iterable[str], default: str = "") -> str:
    """Fetch the first matching header value from label:value lines."""
    mapping = extract_header_map(text)
    for label in labels:
        value = mapping.get(normalize_for_match(label), "")
        if value:
            return value
    return default


def extract_section_block(
    text: str,
    labels: Iterable[str],
    *,
    max_lines: int = 12,
) -> str:
    """Extract a short multi-line section that starts after a known label."""
    lines = str(text or "").splitlines()
    label_set = {normalize_for_match(label) for label in labels}
    for index, raw_line in enumerate(lines):
        if ":" not in raw_line:
            continue
        label, _, remainder = raw_line.partition(":")
        normalized_label = normalize_for_match(label)
        if normalized_label not in label_set:
            continue

        collected: list[str] = []
        if normalize_whitespace(remainder):
            collected.append(normalize_whitespace(remainder))

        cursor = index + 1
        while cursor < len(lines) and len(collected) < max_lines:
            candidate = lines[cursor].rstrip()
            stripped = candidate.strip()
            if stripped and _SECTION_STOP_RE.match(stripped):
                break
            if not stripped:
                if collected:
                    break
                cursor += 1
                continue
            collected.append(normalize_whitespace(stripped))
            cursor += 1

        block = "\n".join(collected).strip()
        if block:
            return block
    return ""


def infer_report_id(source_path: str, text: str) -> str:
    """Return the explicit report ID from the text or filename."""
    header_value = extract_header_value(text, _REPORT_LABELS)
    if header_value:
        match = _REPORT_ID_RE.search(header_value)
        if match:
            return match.group(0).upper()
        return normalize_whitespace(header_value)

    file_name = Path(str(source_path or "")).name
    match = _REPORT_ID_RE.search(file_name)
    if match:
        return match.group(0).upper()
    return ""


def parse_report_date(date_raw: str, *, fallback_mtime_ns: int | None = None) -> tuple[str, int | None]:
    """Convert a report header date into ISO date and year."""
    cleaned = normalize_whitespace(date_raw)
    formats = (
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d %B %Y",
        "%d %b %Y",
    )
    if cleaned:
        for fmt in formats:
            try:
                parsed = datetime.strptime(cleaned, fmt)
                return parsed.date().isoformat(), parsed.year
            except ValueError:
                continue
    if fallback_mtime_ns:
        try:
            fallback_dt = datetime.fromtimestamp(
                float(fallback_mtime_ns) / 1_000_000_000,
                tz=timezone.utc,
            )
            return fallback_dt.date().isoformat(), fallback_dt.year
        except (OSError, OverflowError, ValueError):
            pass
    return "", None


def canonicalize_site(site_raw: str, *, source_path: str = "") -> str:
    """Normalize site naming for SQL grouping/filtering."""
    site = normalize_whitespace(site_raw)
    if not site:
        file_stem = Path(str(source_path or "")).stem
        parts = file_stem.split("_")
        if len(parts) >= 3:
            site = " ".join(parts[2:])
    site = site.replace("\\", " ").replace("/", " ")
    site = re.sub(r"\s+", " ", site).strip(" -_,")
    return titleize_preserving_tokens(site)


def infer_country(site_raw: str, source_path: str = "") -> str:
    """Infer a coarse country/territory grouping from site or path text."""
    haystack = f"{site_raw} {Path(str(source_path or '')).stem}"
    normalized = normalize_for_match(haystack)
    for alias, canonical in sorted(_COUNTRY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in normalized:
            return canonical
    for region in sorted(_US_REGION_TOKENS, key=len, reverse=True):
        if region in normalized:
            return "United States"
    cleaned_site = canonicalize_site(site_raw, source_path=source_path)
    return cleaned_site if cleaned_site else ""


def detect_document_family(text: str, source_path: str = "") -> str:
    """Classify a report-ish document family from explicit headers or file names."""
    normalized = normalize_for_match(text[:800])
    path_norm = normalize_for_match(source_path)
    if "field service report" in normalized or "fsr" in path_norm:
        return "field_service_report"
    if "unscheduled maintenance report" in normalized or "umr" in path_norm:
        return "unscheduled_maintenance_report"
    if "incident report" in normalized or re.search(r"\bir-\d+", path_norm):
        return "incident_report"
    if "site survey" in normalized:
        return "site_survey_report"
    if "installation report" in normalized or "installation checklist" in normalized:
        return "installation_report"
    return ""


def map_report_semantics(
    *,
    document_family: str,
    visit_type: str = "",
    priority: str = "",
    category: str = "",
    source_path: str = "",
    text: str = "",
) -> tuple[str, str]:
    """Map legacy/synthetic report names into production-facing semantics."""
    normalized_visit = normalize_for_match(visit_type)
    normalized_priority = normalize_for_match(priority)
    normalized_category = normalize_for_match(category)
    normalized_text = normalize_for_match(text[:1600])
    normalized_path = normalize_for_match(source_path)

    if not document_family and not _REPORT_ID_RE.search(source_path) and "report" not in normalized_text:
        return "", ""

    report_family = "MSR"

    if "installation" in normalized_visit or "installation" in normalized_text:
        return report_family, "installation"
    if "site survey" in normalized_visit or "site survey" in normalized_text:
        return report_family, "site_survey"
    if (
        document_family == "unscheduled_maintenance_report"
        or "emergency" in normalized_priority
        or "unscheduled" in normalized_priority
        or "emergency" in normalized_visit
        or "unscheduled" in normalized_visit
        or "incident" in normalized_category
    ):
        return report_family, "RTS"
    if document_family in {
        "field_service_report",
        "installation_report",
        "site_survey_report",
    }:
        return report_family, "ASV"
    if document_family == "incident_report":
        return report_family, "unknown"
    if "fsr" in normalized_path:
        return report_family, "ASV"
    if "umr" in normalized_path:
        return report_family, "RTS"
    return report_family, "unknown"


def infer_issue_category(
    *,
    text: str,
    category_raw: str = "",
    failure_mode: str = "",
    call_description: str = "",
) -> str:
    """Normalize issue categories for SQL filters and counts."""
    haystack = normalize_for_match(" ".join([category_raw, failure_mode, call_description, text[:2000]]))
    if "lightning" in haystack:
        return "lightning"
    if any(term in haystack for term in ("power surge", "power event", "brownout", "power outage", "voltage", "surge")):
        return "power"
    if any(term in haystack for term in ("software", "communications", "communication", "vpn", "network")):
        return "software_communications"
    if any(term in haystack for term in ("transmitter", "receiver", "control card", "rf", "hardware", "pll fault")):
        return "hardware"
    return "unknown"


def normalize_action_type(
    action_raw: str,
    *,
    new_unit_serial: str = "",
    removed_serial: str = "",
    failed_unit_serial: str = "",
    installed_serial: str = "",
) -> str:
    """Normalize action text into a compact queryable action type."""
    normalized = normalize_for_match(action_raw)
    for action_type, synonyms in _ACTION_SYNONYMS:
        if any(token in normalized for token in synonyms):
            return action_type
    if new_unit_serial and (removed_serial or failed_unit_serial):
        return "replaced"
    if new_unit_serial or installed_serial:
        return "installed"
    if removed_serial or failed_unit_serial:
        return "removed"
    return "other"


def extract_poc_fields(text: str) -> dict[str, str]:
    """Extract a point-of-contact block plus common nested fields."""
    poc_block = extract_section_block(text, _POC_LABELS, max_lines=8)
    if not poc_block:
        return {
            "poc_name": "",
            "poc_title": "",
            "poc_org": "",
            "poc_phone": "",
            "poc_email": "",
            "poc_address_raw": "",
            "poc_block_raw": "",
        }

    lines = [normalize_whitespace(line) for line in poc_block.splitlines() if normalize_whitespace(line)]
    fields = {
        "poc_name": "",
        "poc_title": "",
        "poc_org": "",
        "poc_phone": "",
        "poc_email": "",
        "poc_address_raw": "",
        "poc_block_raw": poc_block,
    }

    mapping = extract_header_map(poc_block)
    fields["poc_name"] = mapping.get("name", "") or mapping.get("contact", "")
    fields["poc_title"] = mapping.get("title", "")
    fields["poc_org"] = mapping.get("organization", "") or mapping.get("org", "")
    fields["poc_phone"] = mapping.get("phone", "") or mapping.get("telephone", "")
    fields["poc_email"] = mapping.get("email", "")
    fields["poc_address_raw"] = mapping.get("address", "")

    if not fields["poc_name"] and lines:
        fields["poc_name"] = lines[0]
    if not fields["poc_email"]:
        match = _EMAIL_RE.search(poc_block)
        if match:
            fields["poc_email"] = match.group(0)
    if not fields["poc_phone"]:
        match = _PHONE_RE.search(poc_block)
        if match:
            fields["poc_phone"] = normalize_whitespace(match.group(0))
    if not fields["poc_address_raw"] and len(lines) > 1:
        address_lines = [line for line in lines[1:] if not _EMAIL_RE.search(line) and not _PHONE_RE.search(line)]
        if address_lines:
            fields["poc_address_raw"] = "\n".join(address_lines)

    return fields


def extract_report_metadata(
    text: str,
    source_path: str,
    *,
    created_at: str = "",
    fallback_mtime_ns: int | None = None,
) -> dict[str, object]:
    """Extract document-level structured fields from a report-like chunk."""
    document_family = detect_document_family(text, source_path)
    report_id = infer_report_id(source_path, text)
    report_date_raw = extract_header_value(text, _DATE_LABELS)
    report_date_iso, report_year = parse_report_date(
        report_date_raw,
        fallback_mtime_ns=fallback_mtime_ns,
    )
    site_raw = extract_header_value(text, _SITE_LABELS)
    site_canonical = canonicalize_site(site_raw, source_path=source_path)
    country_canonical = infer_country(site_raw, source_path)
    system_name = extract_header_value(text, _SYSTEM_LABELS)
    visit_type_raw = extract_header_value(text, _VISIT_TYPE_LABELS)
    priority_raw = extract_header_value(text, _PRIORITY_LABELS)
    category_raw = extract_header_value(text, _CATEGORY_LABELS)
    report_family, report_subtype = map_report_semantics(
        document_family=document_family,
        visit_type=visit_type_raw,
        priority=priority_raw,
        category=category_raw,
        source_path=source_path,
        text=text,
    )
    if not document_family and not report_id and not (report_date_raw and site_raw and system_name):
        report_family = ""
        report_subtype = ""
    poc_fields = extract_poc_fields(text)

    return {
        "document_family": document_family,
        "report_family": report_family,
        "report_subtype": report_subtype,
        "report_id": report_id,
        "report_date_raw": report_date_raw,
        "report_date_iso": report_date_iso,
        "report_year": report_year,
        "site_raw": site_raw,
        "site_canonical": site_canonical,
        "country_canonical": country_canonical,
        "system_name": normalize_whitespace(system_name),
        "visit_type_raw": normalize_whitespace(visit_type_raw),
        "priority_raw": normalize_whitespace(priority_raw),
        "category_raw": normalize_whitespace(category_raw),
        "follow_on_actions_raw": extract_section_block(text, _FOLLOW_ON_LABELS, max_lines=10),
        "corrective_action_raw": extract_section_block(text, _CORRECTIVE_ACTION_LABELS, max_lines=10),
        "repair_summary_raw": extract_section_block(text, _REPAIR_SUMMARY_LABELS, max_lines=10),
        "reported_by_raw": extract_header_value(text, _REPORTED_BY_LABELS),
        "created_at": normalize_whitespace(created_at),
        **poc_fields,
    }


def is_report_like(metadata: dict[str, object]) -> bool:
    """Return True when a document looks like a service/incident report."""
    return bool(
        metadata.get("report_id")
        or metadata.get("report_family")
        or metadata.get("document_family")
    )


def parse_file_metadata(source_path: str) -> tuple[str, int | None, int | None]:
    """Return file extension, size bytes, and mtime ns if the source still exists."""
    try:
        stat_result = os.stat(source_path)
        return (
            str(Path(source_path).suffix.lower()),
            int(stat_result.st_size),
            int(getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000))),
        )
    except (FileNotFoundError, OSError, ValueError):
        return str(Path(str(source_path or "")).suffix.lower()), None, None


def extract_question_filters(
    question: str,
    *,
    known_sites: Iterable[str] = (),
    known_countries: Iterable[str] = (),
) -> dict[str, object]:
    """Parse coarse structured filters and intent from a natural-language question."""
    raw = str(question or "").strip()
    normalized = normalize_for_match(raw)
    padded = f" {normalized} "

    years = [int(match) for match in _YEAR_RE.findall(raw)]
    range_match = _YEAR_RANGE_RE.search(raw)
    year_start = year_end = None
    if range_match:
        year_start, year_end = sorted((int(range_match.group(1)), int(range_match.group(2))))
    elif years:
        year_start = min(years)
        year_end = max(years)

    subtypes = []
    for label, aliases in {
        "ASV": ("asv", "annual service visit", "scheduled calibration", "scheduled"),
        "RTS": ("rts", "return to service", "unscheduled", "emergency"),
        "installation": ("installation", "install"),
        "site_survey": ("site survey", "survey"),
    }.items():
        if any(f" {normalize_for_match(alias)} " in padded for alias in aliases):
            subtypes.append(label)

    def _match_terms(terms: Iterable[str]) -> list[str]:
        matched: list[str] = []
        for term in sorted({normalize_whitespace(item) for item in terms if normalize_whitespace(item)}, key=len, reverse=True):
            norm_term = normalize_for_match(term)
            if not norm_term:
                continue
            if f" {norm_term} " in padded:
                matched.append(term)
        return matched

    sites = _match_terms(known_sites)
    countries = _match_terms(known_countries)

    top_n = None
    top_match = re.search(r"\btop\s+(\d+)\b", normalized)
    if top_match:
        top_n = int(top_match.group(1))
    else:
        leading_rank_match = re.search(r"\b(\d+)\s+(?:highest|top|worst|best)\b", normalized)
        if leading_rank_match:
            top_n = int(leading_rank_match.group(1))

    action_types: list[str] = []
    for action_type in ("replaced", "installed", "removed", "repaired", "inspected", "adjusted", "upgraded"):
        stem = normalize_for_match(action_type[:-1])
        full = normalize_for_match(action_type)
        if f" {stem} " in padded or f" {full} " in padded:
            action_types.append(action_type)

    wants_summary = any(term in normalized for term in ("summary", "summarize", "overview"))
    wants_list = any(term in normalized for term in ("list ", "show ", "which ", "what parts", "what sites", "who "))
    wants_count = any(term in normalized for term in ("count", "how many", "number of"))
    wants_ranking = any(term in normalized for term in ("top ", "highest", "ranked", "most "))
    asks_poc = "point of contact" in normalized or re.search(r"\bpoc\b", normalized) is not None
    asks_follow_on = "follow on" in normalized or "follow-on" in raw.lower()
    asks_repair = any(term in normalized for term in ("repair", "fix", "corrective action", "repair summary"))
    asks_sites = "site" in normalized or "sites" in normalized
    asks_parts = "part" in normalized or "parts" in normalized
    asks_power = any(term in normalized for term in ("lightning", "power surge", "power surges", "power event", "brownout", "strike"))

    return {
        "question": raw,
        "normalized_question": normalized,
        "years": sorted(set(years)),
        "year_start": year_start,
        "year_end": year_end,
        "report_subtypes": sorted(set(subtypes)),
        "site_terms": sites,
        "country_terms": countries,
        "top_n": top_n,
        "action_types": sorted(set(action_types)),
        "wants_summary": wants_summary,
        "wants_list": wants_list,
        "wants_count": wants_count,
        "wants_ranking": wants_ranking,
        "asks_poc": asks_poc,
        "asks_follow_on": asks_follow_on,
        "asks_repair": asks_repair,
        "asks_sites": asks_sites,
        "asks_parts": asks_parts,
        "asks_power": asks_power,
    }


def clamp_top_n(value: int | None, *, default: int = 10, minimum: int = 1, maximum: int = 100) -> int:
    """Clamp a ranking/list limit into a safe SQLite/reporting range."""
    if value is None:
        return default
    return max(minimum, min(maximum, int(value)))
