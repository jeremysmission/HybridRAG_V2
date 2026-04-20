"""
SQLite sidecar store for typed source metadata used by retrieval.

This is the smallest durable bridge between CorpusForge's path-heavy export
surface and V2's retrieval needs: one row per source document, keyed by the
document's ``source_path``.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


_CDRL_RE = re.compile(r"(?<![A-Z0-9])(A\d{3})(?!\d)", re.IGNORECASE)
_INCIDENT_RE = re.compile(
    r"\b(?:(enterprise program(?:I|CC))[-_ ]?(\d+)|(igsi|igscc)[-_ ]?(\d+))\b",
    re.IGNORECASE,
)
_PO_RE = re.compile(r"\b(?:PO[-_ ]*)?(5\d{9}|7\d{9})\b", re.IGNORECASE)
_CONTRACT_RE = re.compile(
    r"\b(FA[A-Z0-9]{11}|47QFRA[A-Z0-9]{7}|[A-Z]{2}\d{4}-\d{2}-[A-Z]-\d{4})\b",
    re.IGNORECASE,
)

_SITE_ALIASES: dict[str, tuple[str, str]] = {
    "american samoa": ("american samoa", "American Samoa"),
    "ascension": ("ascension", "Ascension"),
    "awase": ("awase", "Awase"),
    "azores": ("azores", "Azores"),
    "curacao": ("curacao", "Curacao"),
    "diego garcia": ("diego garcia", "Diego Garcia"),
    "djibouti": ("djibouti", "Djibouti"),
    "eglin": ("eglin", "Eglin"),
    "fairford": ("fairford", "Fairford"),
    "guam": ("guam", "Guam"),
    "hawaii": ("hawaii", "Hawaii"),
    "kwajalein": ("kwajalein", "Kwajalein"),
    "learmonth": ("learmonth", "Learmonth"),
    "lualualei": ("lualualei", "Lualualei"),
    "misawa": ("misawa", "Misawa"),
    "niger": ("niger", "Niger"),
    "okinawa": ("okinawa", "Okinawa"),
    "palau": ("palau", "Palau"),
    "thule": ("thule", "Thule"),
    "pituffik": ("thule", "Thule"),
    "vandenberg": ("vandenberg", "Vandenberg"),
    "wake": ("wake", "Wake"),
    "alpena": ("alpena", "Alpena"),
}

_SHIPMENT_MODE_TERMS: dict[str, tuple[str, ...]] = {
    "mil-air": ("mil-air", "mil air"),
    "hand carry": ("hand carry", "hand-carry"),
    "comm": ("comm", "commercial"),
}

_CONTRACT_PERIOD_TERMS: tuple[tuple[str, str], ...] = (
    ("oy1", "OY1"),
    ("oy2", "OY2"),
    ("base year", "Base Year"),
)

_PROGRAM_NAME_TERMS: tuple[tuple[str, str], ...] = (
    ("monitoring system", "monitoring system"),
    ("legacy monitoring system", "legacy monitoring system"),
)

_DOCUMENT_TYPE_TERMS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("packing list",), "Packing List"),
    (("bom archive", "bill of materials", "priced bill of materials", "bom"), "BOM"),
    (("shipping", "shipments", "shipment"), "Shipping"),
)

_DOCUMENT_CATEGORY_TERMS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "plans and controls",
            "annual security controls",
            "annual security control and plan review",
            "annual security controls and plans",
            "rmf authorization",
            "security plan",
            "cybersecurity",
            "scap",
            "stig",
            "monthly tcno-iavm",
            "monthly scans-poams",
            "information assurance",
            "system security files",
        ),
        "Security",
    ),
    (
        (
            "10.0 program management",
            "program management",
            "001_project_management",
            "project_management",
            "weekly variance reports",
            "travel approval forms",
            "expense reports",
            "contract deliverable documents",
        ),
        "PM",
    ),
    (
        (
            "5.0 logistics",
            "logistics",
            "packing list",
            "shipping",
            "shipments",
            "purchases",
            "open_purchases",
            "government_property",
            "gfp_gfe",
            "iuid",
        ),
        "Logistics",
    ),
)


@dataclass
class SourceMetadata:
    """Structured helper object used by the retrieval metadata store workflow."""
    source_path: str
    source_ext: str = ""
    cdrl_code: str = ""
    incident_id: str = ""
    po_number: str = ""
    contract_number: str = ""
    site_token: str = ""
    site_full_name: str = ""
    is_reference_did: bool = False
    is_filed_deliverable: bool = False
    shipment_mode: str = ""
    contract_period: str = ""
    program_name: str = ""
    document_type: str = ""
    document_category: str = ""
    source_doc_hash: str = ""

    def to_row(self) -> tuple:
        return (
            self.source_path,
            self.source_ext,
            self.cdrl_code,
            self.incident_id,
            self.po_number,
            self.contract_number,
            self.site_token,
            self.site_full_name,
            int(self.is_reference_did),
            int(self.is_filed_deliverable),
            self.shipment_mode,
            self.contract_period,
            self.program_name,
            self.document_type,
            self.document_category,
            self.source_doc_hash,
        )


def resolve_retrieval_metadata_db_path(lance_db_path: str | Path) -> Path:
    """Store typed retrieval metadata alongside the LanceDB directory."""
    lance_path = Path(lance_db_path)
    parent = lance_path if lance_path.suffix else lance_path.parent if lance_path.name else lance_path
    if lance_path.is_dir() or lance_path.suffix == "":
        parent = lance_path.parent
    return parent / "retrieval_metadata.sqlite3"


def _normalize_path(source_path: str) -> str:
    """Support the retrieval metadata store workflow by handling the normalize path step."""
    return str(source_path or "").replace("/", "\\")


def _normalize_ext(value: str) -> str:
    """Support the retrieval metadata store workflow by handling the normalize ext step."""
    ext = str(value or "").strip().lower()
    if not ext:
        return ""
    return ext if ext.startswith(".") else f".{ext}"


def _normalize_incident(value: str) -> str:
    """Support the retrieval metadata store workflow by handling the normalize incident step."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = _INCIDENT_RE.search(raw)
    if match:
        if match.group(1) and match.group(2):
            return f"{match.group(1).upper()}-{match.group(2)}"
        if match.group(3) and match.group(4):
            return f"{match.group(3).upper()}-{match.group(4)}"
    return raw.upper().replace("_", "-")


def _normalize_contract(value: str) -> str:
    """Support the retrieval metadata store workflow by handling the normalize contract step."""
    return str(value or "").strip().upper()


def _normalize_cdrl(value: str) -> str:
    """Support the retrieval metadata store workflow by handling the normalize cdrl step."""
    return str(value or "").strip().upper()


def _normalize_site_token(value: str) -> str:
    """Support the retrieval metadata store workflow by handling the normalize site token step."""
    return str(value or "").strip().lower()


def _normalize_site_full_name(value: str) -> str:
    """Support the retrieval metadata store workflow by handling the normalize site full name step."""
    return str(value or "").strip()


def _as_bool(value: object) -> bool:
    """Support the retrieval metadata store workflow by handling the as bool step."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _merge_metadata(base: SourceMetadata, new: SourceMetadata) -> SourceMetadata:
    """Support the retrieval metadata store workflow by handling the merge metadata step."""
    return SourceMetadata(
        source_path=base.source_path or new.source_path,
        source_ext=base.source_ext or new.source_ext,
        cdrl_code=base.cdrl_code or new.cdrl_code,
        incident_id=base.incident_id or new.incident_id,
        po_number=base.po_number or new.po_number,
        contract_number=base.contract_number or new.contract_number,
        site_token=base.site_token or new.site_token,
        site_full_name=base.site_full_name or new.site_full_name,
        is_reference_did=base.is_reference_did or new.is_reference_did,
        is_filed_deliverable=base.is_filed_deliverable or new.is_filed_deliverable,
        shipment_mode=base.shipment_mode or new.shipment_mode,
        contract_period=base.contract_period or new.contract_period,
        program_name=base.program_name or new.program_name,
        document_type=base.document_type or new.document_type,
        document_category=base.document_category or new.document_category,
        source_doc_hash=base.source_doc_hash or new.source_doc_hash,
    )


def _detect_site(source_path: str) -> tuple[str, str]:
    """Support the retrieval metadata store workflow by handling the detect site step."""
    lower = source_path.lower()
    matches: list[tuple[int, int, str, str]] = []
    for alias, (token, full_name) in _SITE_ALIASES.items():
        idx = lower.rfind(alias)
        if idx >= 0:
            matches.append((idx, len(alias), token, full_name))
    if not matches:
        return "", ""
    _, _, token, full_name = max(matches)
    return token, full_name


def _detect_first_label(source_path: str, candidates: tuple[tuple[str, str], ...]) -> str:
    """Pick the last occurring canonical label from the path when multiple match."""
    lower = source_path.lower()
    matches: list[tuple[int, int, str]] = []
    for needle, label in candidates:
        idx = lower.rfind(needle)
        if idx >= 0:
            matches.append((idx, len(needle), label))
    if not matches:
        return ""
    _, _, label = max(matches)
    return label


def _detect_group_label(source_path: str, candidates: tuple[tuple[tuple[str, ...], str], ...]) -> str:
    """Pick the last occurring grouped label from the path when multiple match."""
    lower = source_path.lower()
    matches: list[tuple[int, int, str]] = []
    for needles, label in candidates:
        for needle in needles:
            idx = lower.rfind(needle)
            if idx >= 0:
                matches.append((idx, len(needle), label))
    if not matches:
        return ""
    _, _, label = max(matches)
    return label


def derive_source_metadata(source_path: str, chunk: dict | None = None) -> SourceMetadata:
    """Derive the minimal typed retrieval fields from a source path and chunk metadata."""
    chunk = chunk or {}
    raw_path = str(source_path or "").strip()
    normalized_path = _normalize_path(raw_path)
    lower = normalized_path.lower()
    path_obj = Path(normalized_path)

    cdrl_match = _CDRL_RE.search(normalized_path)
    incident_match = _INCIDENT_RE.search(normalized_path)
    po_match = _PO_RE.search(normalized_path)
    contract_match = _CONTRACT_RE.search(normalized_path)
    site_token, site_full_name = _detect_site(lower)

    is_reference_did = (
        "\\dids\\" in lower
        or "/dids/" in lower
        or "data item description" in lower
        or path_obj.name.lower().startswith("di-")
    )
    is_filed_deliverable = (
        not is_reference_did
        and any(
            token in lower
            for token in (
                "\\1.5 enterprise program cdrls\\",
                "/1.5 enterprise program cdrls/",
                "deliverables report",
                "\\contract deliverable documents\\",
                "/contract deliverable documents/",
            )
        )
    )

    shipment_mode = ""
    for canonical, tokens in _SHIPMENT_MODE_TERMS.items():
        if any(token in lower for token in tokens):
            shipment_mode = canonical
            break
    contract_period = _detect_first_label(lower, _CONTRACT_PERIOD_TERMS)
    program_name = _detect_first_label(lower, _PROGRAM_NAME_TERMS)
    document_type = _detect_group_label(lower, _DOCUMENT_TYPE_TERMS)
    document_category = _detect_group_label(lower, _DOCUMENT_CATEGORY_TERMS)

    derived = SourceMetadata(
        source_path=raw_path,
        source_ext=_normalize_ext(path_obj.suffix.lower()),
        cdrl_code=_normalize_cdrl(cdrl_match.group(1) if cdrl_match else ""),
        incident_id=_normalize_incident(
            (
                f"{incident_match.group(1)}-{incident_match.group(2)}"
                if incident_match and incident_match.group(1) and incident_match.group(2)
                else (
                    f"{incident_match.group(3)}-{incident_match.group(4)}"
                    if incident_match and incident_match.group(3) and incident_match.group(4)
                    else ""
                )
            )
        ),
        po_number=str(po_match.group(1)) if po_match else "",
        contract_number=_normalize_contract(contract_match.group(1) if contract_match else ""),
        site_token=site_token,
        site_full_name=site_full_name,
        is_reference_did=is_reference_did,
        is_filed_deliverable=is_filed_deliverable,
        shipment_mode=shipment_mode,
        contract_period=contract_period,
        program_name=program_name,
        document_type=document_type,
        document_category=document_category,
        source_doc_hash=str(chunk.get("source_doc_hash") or chunk.get("doc_hash") or "").strip(),
    )

    chunk_supplied = SourceMetadata(
        source_path=raw_path,
        source_ext=_normalize_ext(str(chunk.get("source_ext") or "")),
        cdrl_code=_normalize_cdrl(str(chunk.get("cdrl_code") or "")),
        incident_id=_normalize_incident(str(chunk.get("incident_id") or chunk.get("igsi") or "")),
        po_number=str(chunk.get("po_number") or "").strip(),
        contract_number=_normalize_contract(str(chunk.get("contract_number") or "")),
        site_token=_normalize_site_token(str(chunk.get("site_token") or "")),
        site_full_name=_normalize_site_full_name(str(chunk.get("site_full_name") or "")),
        is_reference_did=_as_bool(chunk.get("is_reference_did")),
        is_filed_deliverable=_as_bool(chunk.get("is_filed_deliverable")),
        shipment_mode=str(chunk.get("shipment_mode") or "").strip().lower(),
        contract_period=str(chunk.get("contract_period") or "").strip(),
        program_name=str(chunk.get("program_name") or "").strip().upper(),
        document_type=str(chunk.get("document_type") or "").strip(),
        document_category=str(chunk.get("document_category") or "").strip(),
        source_doc_hash=str(chunk.get("source_doc_hash") or chunk.get("doc_hash") or "").strip(),
    )
    return _merge_metadata(chunk_supplied, derived)


class RetrievalMetadataStore:
    """One-row-per-source SQLite sidecar used for typed retrieval lookups."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=memory")
        self._conn.execute("PRAGMA cache_size=-32000")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_metadata (
                source_path TEXT PRIMARY KEY,
                source_ext TEXT NOT NULL DEFAULT '',
                cdrl_code TEXT NOT NULL DEFAULT '',
                incident_id TEXT NOT NULL DEFAULT '',
                po_number TEXT NOT NULL DEFAULT '',
                contract_number TEXT NOT NULL DEFAULT '',
                site_token TEXT NOT NULL DEFAULT '',
                site_full_name TEXT NOT NULL DEFAULT '',
                is_reference_did INTEGER NOT NULL DEFAULT 0,
                is_filed_deliverable INTEGER NOT NULL DEFAULT 0,
                shipment_mode TEXT NOT NULL DEFAULT '',
                contract_period TEXT NOT NULL DEFAULT '',
                program_name TEXT NOT NULL DEFAULT '',
                document_type TEXT NOT NULL DEFAULT '',
                document_category TEXT NOT NULL DEFAULT '',
                source_doc_hash TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_source_metadata_cdrl ON source_metadata(cdrl_code);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_incident ON source_metadata(incident_id);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_po ON source_metadata(po_number);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_contract ON source_metadata(contract_number);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_site_token ON source_metadata(site_token);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_site_name ON source_metadata(site_full_name);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_ref_did ON source_metadata(is_reference_did);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_filed ON source_metadata(is_filed_deliverable);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_ext ON source_metadata(source_ext);
            """
        )
        # Migrate existing databases: add new columns if missing
        existing_columns = {
            str(row[1])
            for row in self._conn.execute("PRAGMA table_info(source_metadata)").fetchall()
        }
        for column_name in (
            "contract_period",
            "program_name",
            "document_type",
            "document_category",
        ):
            if column_name in existing_columns:
                continue
            self._conn.execute(
                f"ALTER TABLE source_metadata ADD COLUMN {column_name} TEXT NOT NULL DEFAULT ''"
            )
        self._conn.commit()
        # Create indexes for new columns (must be AFTER ALTER TABLE migration)
        self._conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_source_metadata_contract_period ON source_metadata(contract_period);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_program_name ON source_metadata(program_name);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_document_type ON source_metadata(document_type);
            CREATE INDEX IF NOT EXISTS idx_source_metadata_document_category ON source_metadata(document_category);
        """)
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS chunk_metadata (
                chunk_id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL DEFAULT '',
                document_id TEXT NOT NULL DEFAULT '',
                canonical_doc_id TEXT NOT NULL DEFAULT '',
                version_id TEXT NOT NULL DEFAULT '',
                parent_chunk_id TEXT NOT NULL DEFAULT '',
                section_path TEXT NOT NULL DEFAULT '',
                page_number INTEGER,
                table_id TEXT NOT NULL DEFAULT '',
                document_family TEXT NOT NULL DEFAULT '',
                effective_date TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chunk_metadata_source ON chunk_metadata(source_path);
            CREATE INDEX IF NOT EXISTS idx_chunk_metadata_doc_id ON chunk_metadata(document_id);
            CREATE INDEX IF NOT EXISTS idx_chunk_metadata_family ON chunk_metadata(document_family);
        """)

    def upsert_from_chunks(self, chunks: list[dict]) -> dict[str, int]:
        """Derive and upsert one metadata row per unique source_path."""
        unique: dict[str, SourceMetadata] = {}
        for chunk in chunks:
            source_path = str(chunk.get("source_path") or "").strip()
            if not source_path:
                continue
            derived = derive_source_metadata(source_path, chunk)
            existing = unique.get(derived.source_path)
            unique[derived.source_path] = _merge_metadata(existing, derived) if existing else derived

        if not unique:
            return {
                "source_count": 0,
                "with_cdrl_code": 0,
                "with_incident_id": 0,
                "with_po_number": 0,
                "with_contract_number": 0,
                "with_site": 0,
                "reference_dids": 0,
                "filed_deliverables": 0,
                "with_contract_period": 0,
                "with_program_name": 0,
                "with_document_type": 0,
                "with_document_category": 0,
            }

        rows = [record.to_row() for record in unique.values()]
        self._conn.executemany(
            """
            INSERT INTO source_metadata (
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_path) DO UPDATE SET
                source_ext = excluded.source_ext,
                cdrl_code = excluded.cdrl_code,
                incident_id = excluded.incident_id,
                po_number = excluded.po_number,
                contract_number = excluded.contract_number,
                site_token = excluded.site_token,
                site_full_name = excluded.site_full_name,
                is_reference_did = excluded.is_reference_did,
                is_filed_deliverable = excluded.is_filed_deliverable,
                shipment_mode = excluded.shipment_mode,
                contract_period = excluded.contract_period,
                program_name = excluded.program_name,
                document_type = excluded.document_type,
                document_category = excluded.document_category,
                source_doc_hash = CASE
                    WHEN excluded.source_doc_hash != '' THEN excluded.source_doc_hash
                    ELSE source_metadata.source_doc_hash
                END,
                updated_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self._conn.commit()

        values = list(unique.values())
        return {
            "source_count": len(values),
            "with_cdrl_code": sum(1 for row in values if row.cdrl_code),
            "with_incident_id": sum(1 for row in values if row.incident_id),
            "with_po_number": sum(1 for row in values if row.po_number),
            "with_contract_number": sum(1 for row in values if row.contract_number),
            "with_site": sum(1 for row in values if row.site_token),
            "reference_dids": sum(1 for row in values if row.is_reference_did),
            "filed_deliverables": sum(1 for row in values if row.is_filed_deliverable),
            "with_contract_period": sum(1 for row in values if row.contract_period),
            "with_program_name": sum(1 for row in values if row.program_name),
            "with_document_type": sum(1 for row in values if row.document_type),
            "with_document_category": sum(1 for row in values if row.document_category),
        }

    _CHUNK_META_FIELDS = (
        "document_id", "canonical_doc_id", "version_id",
        "parent_chunk_id", "section_path", "page_number",
        "table_id", "document_family", "effective_date",
    )

    def upsert_chunk_metadata(self, chunks: list[dict]) -> dict[str, int]:
        """Persist optional per-chunk metadata from enriched exports.

        Only writes rows for chunks that carry at least one of the optional
        fields. Old exports without these fields produce zero inserts.
        """
        rows = []
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "")
            if not chunk_id:
                continue
            has_any = any(chunk.get(f) for f in self._CHUNK_META_FIELDS)
            if not has_any:
                continue
            rows.append((
                chunk_id,
                str(chunk.get("source_path", "")),
                str(chunk.get("document_id", "")),
                str(chunk.get("canonical_doc_id", "")),
                str(chunk.get("version_id", "")),
                str(chunk.get("parent_chunk_id", "")),
                str(chunk.get("section_path", "")),
                chunk.get("page_number"),
                str(chunk.get("table_id", "")),
                str(chunk.get("document_family", "")),
                str(chunk.get("effective_date", "")),
            ))

        if not rows:
            return {"chunks_with_metadata": 0}

        self._conn.executemany(
            """
            INSERT INTO chunk_metadata (
                chunk_id, source_path, document_id, canonical_doc_id,
                version_id, parent_chunk_id, section_path, page_number,
                table_id, document_family, effective_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chunk_id) DO UPDATE SET
                document_id = excluded.document_id,
                canonical_doc_id = excluded.canonical_doc_id,
                version_id = excluded.version_id,
                parent_chunk_id = excluded.parent_chunk_id,
                section_path = excluded.section_path,
                page_number = excluded.page_number,
                table_id = excluded.table_id,
                document_family = excluded.document_family,
                effective_date = excluded.effective_date,
                updated_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self._conn.commit()
        return {"chunks_with_metadata": len(rows)}

    def find_source_paths(
        self,
        *,
        cdrl_code: str | None = None,
        incident_id: str | None = None,
        po_number: str | None = None,
        contract_number: str | None = None,
        site_terms: list[str] | None = None,
        is_reference_did: bool | None = None,
        is_filed_deliverable: bool | None = None,
        source_exts: list[str] | None = None,
        shipment_mode: str | None = None,
        contract_period: str | None = None,
        program_name: str | None = None,
        document_type: str | None = None,
        document_category: str | None = None,
        limit: int = 10,
    ) -> list[str]:
        """Return matching source paths for typed retrieval filters."""
        clauses: list[str] = []
        params: list[object] = []

        if cdrl_code:
            clauses.append("cdrl_code = ?")
            params.append(_normalize_cdrl(cdrl_code))
        if incident_id:
            clauses.append("incident_id = ?")
            params.append(_normalize_incident(incident_id))
        if po_number:
            clauses.append("po_number = ?")
            params.append(str(po_number).strip())
        if contract_number:
            clauses.append("contract_number = ?")
            params.append(_normalize_contract(contract_number))
        if is_reference_did is not None:
            clauses.append("is_reference_did = ?")
            params.append(1 if is_reference_did else 0)
        if is_filed_deliverable is not None:
            clauses.append("is_filed_deliverable = ?")
            params.append(1 if is_filed_deliverable else 0)
        if shipment_mode:
            clauses.append("shipment_mode = ?")
            params.append(str(shipment_mode).strip().lower())
        if contract_period:
            clauses.append("contract_period = ?")
            params.append(str(contract_period).strip())
        if program_name:
            clauses.append("UPPER(program_name) = ?")
            params.append(str(program_name).strip().upper())
        if document_type:
            clauses.append("document_type = ?")
            params.append(str(document_type).strip())
        if document_category:
            clauses.append("document_category = ?")
            params.append(str(document_category).strip())
        if source_exts:
            normalized_exts = [_normalize_ext(ext) for ext in source_exts if ext]
            if normalized_exts:
                placeholders = ", ".join("?" for _ in normalized_exts)
                clauses.append(f"source_ext IN ({placeholders})")
                params.extend(normalized_exts)
        if site_terms:
            normalized_terms = [term.strip().lower() for term in site_terms if term and term.strip()]
            if normalized_terms:
                placeholders = ", ".join("?" for _ in normalized_terms)
                clauses.append(
                    f"(site_token IN ({placeholders}) OR lower(site_full_name) IN ({placeholders}))"
                )
                params.extend(normalized_terms)
                params.extend(normalized_terms)

        if not clauses:
            return []

        sql = (
            "SELECT source_path FROM source_metadata "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY source_path ASC LIMIT ?"
        )
        params.append(max(1, int(limit)))
        rows = self._conn.execute(sql, params).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM source_metadata").fetchone()
        return int(row[0] or 0) if row else 0

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            logger.debug("Failed closing retrieval metadata store", exc_info=True)
