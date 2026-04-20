"""
Deterministic PO-pricing extraction for procurement-cost aggregation.

Two conservative lanes are supported:
  - path-derived extraction when the path contains an explicit PO + price signal
  - chunk-derived extraction from purchase-order / procurement documents
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.extraction.tabular_substrate import detect_logistics_table_families
from src.store.po_pricing_store import POPricingEvent, POPricingStore
from src.store.retrieval_metadata_store import SourceMetadata, derive_source_metadata

logger = logging.getLogger(__name__)

_PO_NUMBER_RE = re.compile(
    r"\b(?:Purchase Order(?: No\.?| Number)?[:#]?\s*|PO[#:\s-]*)"
    r"(?P<po>5\d{9}|7\d{9}|PO-\d{4}-\d{4})\b",
    re.IGNORECASE,
)
_PLAIN_PO_RE = re.compile(r"\b(5\d{9}|7\d{9}|PO-\d{4}-\d{4})\b", re.IGNORECASE)
_PRICE_PAREN_RE = re.compile(
    r"\((?:USD\s*)?\$?(?P<price>\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})\)"
)
_QTY_PATH_RE = re.compile(r"\b(?P<qty>\d+(?:\.\d+)?)\s+each\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{2,4})\b")
_DOT_DATE_RE = re.compile(r"\b(?P<month>\d{1,2})[._-](?P<day>\d{1,2})[._-](?P<year>\d{2,4})\b")
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})(?:T\d{2}:\d{2}:\d{2})?\b")
_DATE_ISSUED_RE = re.compile(r"\bDate Issued\s*(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)
_CREATED_RE = re.compile(r"\bCreated:\s*(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)
_DATE_LABEL_RE = re.compile(r"\bDate\s*[:\-]\s*(\d{1,2}/\d{1,2}/\d{2,4})\b", re.IGNORECASE)
_SUPPLIER_RE = re.compile(
    r"Supplier Information\s+(?:Supplier Number:[^\n]*\n)?(?P<vendor>[^\n]{2,120})",
    re.IGNORECASE,
)
_VENDOR_LINE_RE = re.compile(r"\b(?:Supplier Name|Vendor|Vendor Name):\s*(.+)", re.IGNORECASE)
_PN_FIELD_RE = re.compile(r"\b(?:PN|P/N|Part Number)\s*:\s*([A-Z0-9-]{4,})", re.IGNORECASE)
_PO_TABLE_ROW_RE = re.compile(
    r"(?mi)^\s*(?P<item>\d+)\s+"
    r"(?:(?P<material>[A-Z0-9-]{4,})\s+)?"
    r"(?P<delivery>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<qty>\d+(?:\.\d+)?)\s+\S+\s+"
    r"(?P<unit>\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})\s+"
    r"(?P<extended>\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})\s*$"
)
_QUOTE_ROW_RE = re.compile(
    r"(?mi)^\s*(?P<item>\d+)\s+"
    r"(?P<desc>[^\n$]{4,}?)\s+"
    r"(?P<qty>\d+(?:\.\d+)?)\s+"
    r"\$?(?P<unit>\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+\.\d{2})\s+"
    r"(?P<extended>\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+\.\d{2})\s*\$?\s*$"
)
_NATURAL_DATE_RE = re.compile(
    r"\b(?P<day>\d{1,2})\s*"
    r"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+"
    r"(?P<year>\d{2,4})\b",
    re.IGNORECASE,
)
_MONTHLY_PR_PO_RE = re.compile(
    r"\b(?P<year>20\d{2})[ ._-](?P<month>\d{2})\s+PR\s*&\s*PO(?:\b|_)",
    re.IGNORECASE,
)
_YEAR_ORGANIZED_SHIPMENT_FOLDER_RE = re.compile(r"^(?P<year>20\d{2})\s*-\s*shipments?$", re.IGNORECASE)
_HYPHENATED_PART_RE = re.compile(r"\b[A-Z0-9]{1,10}-[A-Z0-9-]{1,24}\b")
_ALNUM_PART_RE = re.compile(r"\b[A-Z]{2,}[A-Z0-9]{2,}\b")
_MONTH_NAME_TO_NUM = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "SEPT": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
_EXCLUDED_PART_VALUES = {
    "USA",
    "PO",
    "PR",
    "USD",
    "ITEM",
    "TOTAL",
    "OPEN",
    "DATE",
    "LO",
}
_CANDIDATE_PATH_TOKENS = (
    "purchase order",
    "purchase_order",
    "\\purchases\\",
    "\\procurement\\",
    "\\open purchases\\",
    "\\shipments\\",
    "\\contract",
    "\\contracts",
    "\\po ",
    "\\po-",
    "\\po#",
    "(po ",
    " po ",
    "pr & po",
    "pr&po",
    "space report",
    "dd250",
    "dd 250",
    "rcvd",
)
_PO_CONTENT_HINTS = (
    "purchase order",
    "po number",
    "supplier information",
    "supplier name",
    "vendor name",
    "unit price",
    "qty",
    "quantity",
    "part number",
    "p/n",
    "material/description",
    "item description",
)


@dataclass(frozen=True)
class _ParsedPOItem:
    part_number: str
    unit_price: float | None
    quantity: float | None
    delivery_date: str | None


def _parse_float(value: str | None) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_date(raw: str | None) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    iso = _ISO_DATE_RE.search(text)
    if iso:
        return iso.group(1)
    natural = _NATURAL_DATE_RE.search(text)
    if natural:
        year = _normalize_year(natural.group("year"))
        month = _MONTH_NAME_TO_NUM.get(str(natural.group("month") or "").strip().upper())
        day = int(natural.group("day"))
        if year is not None and month is not None:
            return f"{year:04d}-{month:02d}-{day:02d}"
    match = _DATE_RE.search(text) or _DOT_DATE_RE.search(text)
    if not match:
        return None
    year = _normalize_year(match.group("year"))
    if year is None:
        return None
    return f"{year:04d}-{int(match.group('month')):02d}-{int(match.group('day')):02d}"


def _normalize_year(raw: str | None) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        year = int(text)
    except ValueError:
        return None
    if len(text) == 2:
        return 2000 + year if year <= 49 else 1900 + year
    return year


def _compute_lead_time(po_date: str | None, delivery_date: str | None) -> int | None:
    start = _normalize_date(po_date)
    end = _normalize_date(delivery_date)
    if not start or not end:
        return None
    try:
        from datetime import date

        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except ValueError:
        return None
    delta = (end_d - start_d).days
    return delta if delta >= 0 else None


def _extract_po_number(text: str) -> str:
    match = _PO_NUMBER_RE.search(text or "")
    if match:
        return str(match.group("po") or "").upper()
    match = _PLAIN_PO_RE.search(text or "")
    return str(match.group(1) or "").upper() if match else ""


def _extract_vendor(text: str, source_path: str) -> str:
    for pattern in (_SUPPLIER_RE, _VENDOR_LINE_RE):
        match = pattern.search(text or "")
        if match:
            vendor = " ".join(str(match.group(1) if match.lastindex else match.group("vendor")).split())
            if vendor:
                return vendor
    folder = Path(source_path or "").parent.name
    for candidate in reversed(re.findall(r"\(([^()]{2,80})\)", folder)):
        text_candidate = " ".join(candidate.split())
        if not text_candidate:
            continue
        if text_candidate.startswith("$") or text_candidate.upper().startswith("PO "):
            continue
        if _normalize_date(text_candidate):
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", text_candidate):
            continue
        return text_candidate
    return ""


def _extract_part_token(text: str) -> str:
    raw = str(text or "").upper()
    if not raw:
        return ""
    pn_field = _PN_FIELD_RE.search(raw)
    if pn_field:
        candidate = str(pn_field.group(1) or "").strip().upper()
        if _is_valid_part(candidate):
            return candidate
    for pattern in (_HYPHENATED_PART_RE, _ALNUM_PART_RE):
        for match in pattern.finditer(raw):
            candidate = str(match.group(0) or "").strip(" ,.;:()[]{}").upper()
            if _is_valid_part(candidate):
                return candidate
    return ""


def _is_valid_part(candidate: str) -> bool:
    token = str(candidate or "").strip().upper()
    if not token or token in _EXCLUDED_PART_VALUES:
        return False
    if token.startswith("PO-20") or token.startswith("PR-20"):
        return False
    if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", token):
        return False
    if re.fullmatch(r"\d{1,2}-(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)-\d{2,4}", token):
        return False
    if re.fullmatch(r"20\d{2}", token):
        return False
    if re.fullmatch(r"\d{4,}", token):
        return False
    if not re.search(r"\d", token):
        return False
    return True


def _extract_po_date_from_path(source_path: str) -> str | None:
    path = str(source_path or "").replace("/", "\\")
    if not path:
        return None
    monthly = _MONTHLY_PR_PO_RE.search(path)
    if monthly:
        return f"{int(monthly.group('year')):04d}-{int(monthly.group('month')):02d}-01"
    return _normalize_date(path) or _extract_year_folder_hint(path)


def _extract_year_folder_hint(source_path: str) -> str | None:
    normalized = str(source_path or "").replace("/", "\\")
    for part in normalized.split("\\"):
        match = _YEAR_ORGANIZED_SHIPMENT_FOLDER_RE.fullmatch(part.strip())
        if match:
            return f"{int(match.group('year')):04d}-01-01"
    return None


def _extract_po_date(text: str, source_path: str) -> str | None:
    body = str(text or "")
    for pattern in (_DATE_ISSUED_RE, _CREATED_RE, _DATE_LABEL_RE):
        match = pattern.search(body)
        if not match:
            continue
        normalized = _normalize_date(match.group(1))
        if normalized:
            return normalized
    return _extract_po_date_from_path(source_path)


def _detect_system(source_path: str, text: str) -> str:
    lower = f"{source_path}\n{text}".lower()
    if "nexion" in lower or "monitoring system" in lower:
        return "NEXION"
    if "isto" in lower:
        return "ISTO"
    return ""


def is_po_candidate_source_path(source_path: str) -> bool:
    normalized = str(source_path or "").replace("/", "\\").lower()
    if not normalized:
        return False
    if "\\shipments\\" in normalized and _extract_year_folder_hint(source_path):
        return True
    families = detect_logistics_table_families(normalized)
    if "received_po" in families or "dd250" in families:
        return True
    return any(token in normalized for token in _CANDIDATE_PATH_TOKENS)


def _has_po_content_signal(text: str) -> bool:
    body = str(text or "")
    if not body:
        return False
    if _extract_po_number(body):
        return True
    hits = 0
    for line in body.splitlines()[:80]:
        lowered = line.lower()
        if any(hint in lowered for hint in _PO_CONTENT_HINTS):
            hits += 1
        if hits >= 2:
            return True
    families = detect_logistics_table_families("", body)
    return "received_po" in families or "dd250" in families


class POEventExtractor:
    """Recover deterministic PO pricing rows from path + chunk inputs."""

    def extract_from_path(
        self,
        source_path: str,
        *,
        metadata: SourceMetadata | None = None,
    ) -> list[POPricingEvent]:
        normalized_path = str(source_path or "").replace("/", "\\").strip()
        if not normalized_path or not is_po_candidate_source_path(normalized_path):
            return []
        metadata = metadata or derive_source_metadata(normalized_path)
        po_number = metadata.po_number or _extract_po_number(normalized_path)
        price_match = _PRICE_PAREN_RE.search(normalized_path)
        unit_price = _parse_float(price_match.group("price")) if price_match else None
        if not po_number or unit_price is None:
            return []
        part_number = _extract_part_token(normalized_path)
        qty_match = _QTY_PATH_RE.search(normalized_path)
        return [
            POPricingEvent(
                po_number=po_number,
                part_number=part_number,
                unit_price=unit_price,
                qty=_parse_float(qty_match.group("qty")) if qty_match else None,
                po_date=_extract_po_date("", normalized_path),
                vendor=_extract_vendor("", normalized_path),
                lead_time_days=None,
                source_path=normalized_path,
                chunk_id="",
                source_doc_hash=metadata.source_doc_hash,
                system=_detect_system(normalized_path, ""),
                site_token=metadata.site_token,
                extraction_method="path_v1",
                confidence=0.72,
            )
        ]

    def extract_from_chunk(
        self,
        *,
        text: str,
        chunk_id: str,
        source_path: str,
        source_doc_hash: str = "",
        metadata: SourceMetadata | None = None,
    ) -> list[POPricingEvent]:
        normalized_path = str(source_path or "").replace("/", "\\").strip()
        if not normalized_path:
            return []
        metadata = metadata or derive_source_metadata(
            normalized_path,
            {"source_doc_hash": source_doc_hash},
        )
        body = str(text or "")
        if not (
            is_po_candidate_source_path(normalized_path)
            or _extract_po_number(body)
            or _has_po_content_signal(body)
        ):
            return []

        po_number = metadata.po_number or _extract_po_number(body) or _extract_po_number(normalized_path)
        if not po_number:
            return []
        po_date = _extract_po_date(body, normalized_path)
        vendor = _extract_vendor(body, normalized_path)
        system = _detect_system(normalized_path, body)
        site_token = metadata.site_token

        events: list[POPricingEvent] = []
        for item in self._extract_items(body):
            if item.unit_price is None:
                continue
            events.append(
                POPricingEvent(
                    po_number=po_number,
                    part_number=item.part_number,
                    unit_price=item.unit_price,
                    qty=item.quantity,
                    po_date=po_date,
                    vendor=vendor,
                    lead_time_days=_compute_lead_time(po_date, item.delivery_date),
                    source_path=normalized_path,
                    chunk_id=str(chunk_id or ""),
                    source_doc_hash=metadata.source_doc_hash or str(source_doc_hash or ""),
                    system=system,
                    site_token=site_token,
                    extraction_method="chunk_v1",
                    confidence=0.93 if item.part_number else 0.82,
                )
            )

        if events:
            return events

        fallback = self.extract_from_path(normalized_path, metadata=metadata)
        if not fallback:
            return []
        return [
            POPricingEvent(
                **{
                    **event.__dict__,
                    "chunk_id": str(chunk_id or ""),
                    "source_doc_hash": metadata.source_doc_hash or str(source_doc_hash or ""),
                }
            )
            for event in fallback
        ]

    def _extract_items(self, text: str) -> list[_ParsedPOItem]:
        items = self._extract_po_table_items(text)
        if items:
            return items
        return self._extract_quote_items(text)

    def _extract_po_table_items(self, text: str) -> list[_ParsedPOItem]:
        items: list[_ParsedPOItem] = []
        global_part = _extract_part_token(text)
        for match in _PO_TABLE_ROW_RE.finditer(text or ""):
            window = text[match.start(): min(len(text), match.end() + 1200)]
            part_number = (
                _extract_part_token(match.group("material"))
                or _extract_part_token(window)
                or global_part
            )
            items.append(
                _ParsedPOItem(
                    part_number=part_number,
                    unit_price=_parse_float(match.group("unit")),
                    quantity=_parse_float(match.group("qty")),
                    delivery_date=_normalize_date(match.group("delivery")),
                )
            )
        return items

    def _extract_quote_items(self, text: str) -> list[_ParsedPOItem]:
        items: list[_ParsedPOItem] = []
        for match in _QUOTE_ROW_RE.finditer(text or ""):
            description = " ".join(str(match.group("desc") or "").split())
            part_number = _extract_part_token(description)
            if not part_number:
                continue
            items.append(
                _ParsedPOItem(
                    part_number=part_number,
                    unit_price=_parse_float(match.group("unit")),
                    quantity=_parse_float(match.group("qty")),
                    delivery_date=None,
                )
            )
        return items


def populate_from_path_derived(
    metadata_db: str | Path,
    store: POPricingStore,
    *,
    batch_size: int = 5000,
) -> dict[str, int]:
    """Populate path-derived pricing rows from retrieval metadata alone."""
    extractor = POEventExtractor()
    conn = sqlite3.connect(str(metadata_db))
    conn.row_factory = sqlite3.Row
    scanned_rows = 0
    matched_rows = 0
    inserted_rows = 0
    batch: list[POPricingEvent] = []
    try:
        cursor = conn.execute(
            """
            SELECT
                source_path,
                source_ext,
                cdrl_code,
                incident_id,
                po_number,
                contract_number,
                site_token,
                site_full_name,
                is_reference_did,
                is_filed_deliverable,
                shipment_mode,
                contract_period,
                program_name,
                document_type,
                document_category,
                source_doc_hash
            FROM source_metadata
            WHERE po_number != ''
               OR lower(source_path) LIKE '%purchase order%'
               OR lower(source_path) LIKE '%purchase_order%'
               OR lower(source_path) LIKE '%\\purchases\\%'
               OR lower(source_path) LIKE '%\\procurement\\%'
               OR lower(source_path) LIKE '%\\contract%'
               OR source_path LIKE '%PO %'
               OR source_path LIKE '%PO-%'
               OR source_path LIKE '%PO#%'
               OR source_path LIKE '%(PO %'
            """
        )
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                scanned_rows += 1
                row_map = dict(row)
                source_path = str(row_map.get("source_path") or "")
                metadata = derive_source_metadata(source_path, row_map)
                events = extractor.extract_from_path(source_path, metadata=metadata)
                if not events:
                    continue
                matched_rows += len(events)
                batch.extend(events)
            if batch:
                inserted_rows += store.insert_many(batch)
                batch = []
    finally:
        conn.close()
    return {
        "scanned_rows": scanned_rows,
        "matched_rows": matched_rows,
        "inserted_rows": inserted_rows,
        "skipped_rows": matched_rows - inserted_rows,
        "final_count": store.count(),
    }
