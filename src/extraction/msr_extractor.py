"""Path-driven MSR visit extraction for ASV/RTS completion substrates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_DATE_RANGE_PATTERNS = (
    re.compile(
        r"(?P<start>\d{4}-\d{2}-\d{2})\s+thru\s+(?P<end_month>\d{2})-(?P<end_day>\d{2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<start>\d{4}\.\d{2}\.\d{2})-(?P<end>\d{4}\.\d{2}\.\d{2})",
        re.IGNORECASE,
    ),
)


def canonicalize_site_token(raw_site: str) -> str:
    site = str(raw_site or "").strip().lower()
    site = site.replace("&", " and ")
    site = re.sub(r"[^a-z0-9]+", " ", site)
    site = re.sub(r"\s+", " ", site).strip()
    return site.replace(" ", "_")


def _extract_date_range_from_visit_folder(visit_folder: str) -> tuple[str, str, int | None]:
    folder = str(visit_folder or "")
    for pattern in _DATE_RANGE_PATTERNS:
        match = pattern.search(folder)
        if not match:
            continue
        if "end" in match.groupdict():
            start = match.group("start").replace(".", "-")
            end = match.group("end").replace(".", "-")
            return start, end, int(start[:4])
        start = match.group("start")
        end = f"{start[:5]}{match.group('end_month')}-{match.group('end_day')}"
        return start, end, int(start[:4])
    year_match = re.search(r"\b(20\d{2})\b", folder)
    year = int(year_match.group(1)) if year_match else None
    return "", "", year


def _detect_systems(text: str) -> list[str]:
    lowered = str(text or "").lower()
    systems: list[str] = []
    if re.search(r"\bnexio?n\b", lowered):
        systems.append("NEXION")
    if "isto" in lowered:
        systems.append("ISTO")
    if not systems:
        systems.append("")
    return systems


@dataclass
class MSRVisitRecord:
    visit_key: str
    site_token: str
    system: str
    visit_year: int | None
    start_date: str
    end_date: str
    visit_type: str
    source_path: str
    extraction_method: str = "msr_path_v1"
    confidence: float = 0.9


def extract_msr_records_from_path(source_path: str) -> list[MSRVisitRecord]:
    path = Path(str(source_path or ""))
    parts = path.parts
    try:
        sites_index = next(i for i, piece in enumerate(parts) if piece.lower() == "(01) sites")
        site_name = parts[sites_index + 1]
        visit_folder = parts[sites_index + 2]
    except Exception:
        return []

    site_token = canonicalize_site_token(site_name)
    start_date, end_date, visit_year = _extract_date_range_from_visit_folder(visit_folder)
    systems = _detect_systems(" ".join([visit_folder, str(path)]))
    visit_flags: set[str] = set()
    lowered = " ".join([visit_folder, str(path)]).lower()
    if "asv-rts" in lowered or "rts-asv" in lowered:
        visit_flags.update({"ASV", "RTS"})
    else:
        if "asv" in lowered:
            visit_flags.add("ASV")
        if "rts" in lowered:
            visit_flags.add("RTS")
    if not visit_flags:
        return []

    records: list[MSRVisitRecord] = []
    for visit_type in sorted(visit_flags):
        for system in systems:
            visit_key = "|".join(
                [
                    site_token,
                    system or "ANY",
                    visit_type,
                    start_date or visit_folder,
                ]
            )
            records.append(
                MSRVisitRecord(
                    visit_key=visit_key,
                    site_token=site_token,
                    system=system,
                    visit_year=visit_year,
                    start_date=start_date,
                    end_date=end_date,
                    visit_type=visit_type,
                    source_path=str(path),
                )
            )
    return records
