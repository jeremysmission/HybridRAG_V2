"""
Deterministic table extraction for the logistics-first structured substrate.

The clean Tier 1 store proved we have real spreadsheet-like content in the
corpus, but the runtime extraction path was not promoting those rows into the
table store. This module keeps the first production step narrow and auditable:
recover the obvious logistics/tabular shapes that already appear in chunk text.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from src.store.entity_store import TableRow

SPREADSHEET_EXTENSIONS = {".csv", ".tsv", ".xls", ".xlsx"}

LOGISTICS_TABLE_SOURCE_HINTS: dict[str, tuple[str, ...]] = {
    "packing_list": ("packing list", "packing slip"),
    "bom": ("bom", "bill of material", "bill of materials"),
    "received_po": (
        "pr & po",
        "pr&po",
        "space report",
        "received",
        "procurement",
        "rcvd",
    ),
    "dd250": ("dd250", "dd 250"),
    "calibration": ("calibration",),
    "spares_report": ("spare", "inventory"),
}

LOGISTICS_FAMILY_PRIORITY: tuple[str, ...] = (
    "packing_list",
    "bom",
    "received_po",
    "dd250",
    "calibration",
    "spares_report",
    "spreadsheet",
)


def detect_logistics_table_families(source_path: str, text: str = "") -> set[str]:
    """Return source-family hints for logistics-first table extraction."""
    families: set[str] = set()
    path = Path(source_path or "")
    haystack = f"{source_path}\n{text[:800]}".lower()

    if path.suffix.lower() in SPREADSHEET_EXTENSIONS:
        families.add("spreadsheet")

    for family, hints in LOGISTICS_TABLE_SOURCE_HINTS.items():
        if any(hint in haystack for hint in hints):
            families.add(family)

    return families


def pick_primary_logistics_family(families: set[str]) -> str | None:
    """Pick one stable family label for audit reporting."""
    for family in LOGISTICS_FAMILY_PRIORITY:
        if family in families:
            return family
    return None


@dataclass(frozen=True)
class TablePromptContext:
    """Compact prompt-side summary for the first semi-structured A/B lane."""

    table_mode: str
    table_family: str | None
    detected_row_count: int
    header_signatures: tuple[str, ...]
    row_provenance_lines: tuple[str, ...]

    def render(self) -> str:
        """Render a deterministic prompt block for the treatment path."""
        header_block = "\n".join(f"- {item}" for item in self.header_signatures) or "- none"
        provenance_block = "\n".join(f"- {item}" for item in self.row_provenance_lines) or "- none"
        family = self.table_family or "unknown"
        return (
            "[TABLE SYNOPSIS]\n"
            f"table_mode: {self.table_mode}\n"
            f"table_family: {family}\n"
            f"detected_row_count: {self.detected_row_count}\n"
            "header_signatures:\n"
            f"{header_block}\n"
            "row_provenance:\n"
            f"{provenance_block}\n"
            "[/TABLE SYNOPSIS]"
        )


class DeterministicTableExtractor:
    """Recover obvious row-level structure without invoking an LLM."""

    _KEY_TOKEN_RE = re.compile(
        r"(?P<label>[A-Za-z0-9][A-Za-z0-9 /#().%&+?_-]{0,80}?):"
    )
    _CALIBRATION_ROW_RE = re.compile(
        r"^(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+"
        r"(?P<lower>[A-Za-z0-9]+)\s+"
        r"(?P<upper>[A-Za-z0-9]+)\s*$"
    )
    _INVENTORY_HEADER_RE = re.compile(r"^\s*Description\b.*\bQty\b", re.IGNORECASE)
    _TRAILING_QTY_RE = re.compile(r"(?P<body>.+?)\s+(?P<qty>\d+(?:\.\d+)?)\s*$")
    _PART_TOKEN_RE = re.compile(
        r"\b(?:"
        r"[A-Z]{2,}\s*[-‐]\s*[A-Z0-9]{2,}[A-Z0-9-]*"
        r"|[A-Z]{2,}\d{2,}[A-Z0-9-]*"
        r"|\d{5,}[A-Z0-9-]*"
        r")\b"
    )
    _ROW_RE = re.compile(r"^\[ROW\s+(\d+)\]\s*(.+)$", re.IGNORECASE)
    _MIN_LABELS_PER_PIPE_SEGMENT = 3
    _MIN_SEGMENTS_PER_PIPE_RECORD = 1

    def extract(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        """Run the deterministic extractors and merge duplicate rows."""
        rows: list[TableRow] = []
        rows.extend(self._extract_markdown_tables(text, chunk_id, source_path))
        rows.extend(self._extract_bracket_row_tables(text, chunk_id, source_path))
        # Pipe-joined KV rows must run before the legacy line-oriented KV
        # extractor. When the chunk packs several logical rows into one
        # ``|``-separated line, the legacy path collapses them into one
        # mega-row with ``Label 2`` / ``Label 3`` duplicate keys. If pipe
        # extraction succeeded we suppress the legacy path for this chunk
        # to avoid emitting that collapsed garbage alongside the real rows.
        pipe_rows = self._extract_pipe_joined_kv_rows(text, chunk_id, source_path)
        rows.extend(pipe_rows)
        if not pipe_rows:
            rows.extend(self._extract_key_value_tables(text, chunk_id, source_path))
        rows.extend(self._extract_calibration_projection_table(text, chunk_id, source_path))
        rows.extend(self._extract_inventory_rows(text, chunk_id, source_path))
        return self._merge_rows(rows)

    def _extract_pipe_joined_kv_rows(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        """Recover one row per ``|``-separated segment of fully-labeled records.

        Handles the logistics-family shape where multiple logical spreadsheet
        rows are flattened onto a single chunked line with ``|`` separators
        and ``Label: value, Label: value, ...`` content per segment, e.g.
        Initial Spares / BOM exports from SAP-like Excel flatteners.

        The existing ``_extract_key_value_tables`` walks ``text.splitlines()``
        and so collapses all pipe-joined rows into one mega-row with label
        duplicates. This method splits on ``|`` first, then reuses the same
        label parser per segment, giving one TableRow per logical record.
        """
        if "|" not in text:
            return []

        rows: list[TableRow] = []
        table_index = 0
        row_index = 0
        current_headers: list[str] | None = None
        any_record_emitted = False

        for raw_segment in text.split("|"):
            segment = self._normalize_spaces(self._strip_section_prefix(raw_segment))
            if not segment:
                continue

            # Only parse segments that already contain enough labeled tokens
            # to look like a record row. Anything less is likely prose or a
            # header-only pipe cell.
            label_hits = list(self._KEY_TOKEN_RE.finditer(segment))
            if len(label_hits) < self._MIN_LABELS_PER_PIPE_SEGMENT:
                continue

            record = self._parse_key_value_record(segment)
            if len(record) < self._MIN_LABELS_PER_PIPE_SEGMENT:
                continue

            headers = list(record.keys())
            values = list(record.values())

            if headers != current_headers:
                current_headers = headers
                row_index = 0
                table_index += 1

            rows.append(
                TableRow(
                    source_path=source_path,
                    table_id=f"{chunk_id}_pipekv_{table_index}",
                    row_index=row_index,
                    headers=json.dumps(headers),
                    values=json.dumps(values),
                    chunk_id=chunk_id,
                )
            )
            row_index += 1
            any_record_emitted = True

        if not any_record_emitted:
            return []
        return rows

    def _extract_markdown_tables(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        lines = [line.rstrip() for line in text.splitlines()]
        rows: list[TableRow] = []
        table_index = 0
        line_index = 0

        while line_index < len(lines) - 1:
            header_line = lines[line_index].strip()
            separator_line = lines[line_index + 1].strip()
            if not self._looks_like_pipe_row(header_line) or not self._is_markdown_separator(
                separator_line
            ):
                line_index += 1
                continue

            headers = self._split_pipe_row(header_line)
            if not headers:
                line_index += 1
                continue

            table_id = f"{chunk_id}_mdtable_{table_index}"
            table_index += 1
            row_index = 0
            cursor = line_index + 2
            while cursor < len(lines):
                candidate = lines[cursor].strip()
                if not self._looks_like_pipe_row(candidate) or self._is_markdown_separator(
                    candidate
                ):
                    break
                values = self._split_pipe_row(candidate)
                if len(values) == len(headers):
                    rows.append(
                        TableRow(
                            source_path=source_path,
                            table_id=table_id,
                            row_index=row_index,
                            headers=json.dumps(headers),
                            values=json.dumps(values),
                            chunk_id=chunk_id,
                        )
                    )
                    row_index += 1
                cursor += 1
            line_index = cursor

        return rows

    def _extract_bracket_row_tables(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        lines = [line.strip() for line in text.splitlines()]
        rows: list[TableRow] = []
        current_headers: list[str] | None = None
        table_index = 0
        row_index = 0

        for line in lines:
            match = self._ROW_RE.match(line)
            if not match:
                continue

            logical_row = int(match.group(1))
            cells = [cell.strip() for cell in match.group(2).split("|")]
            if self._looks_like_header_row(logical_row, cells):
                current_headers = cells
                row_index = 0
                table_index += 1
                continue

            if not current_headers or len(cells) != len(current_headers):
                continue

            rows.append(
                TableRow(
                    source_path=source_path,
                    table_id=f"{chunk_id}_rowtable_{table_index}",
                    row_index=row_index,
                    headers=json.dumps(current_headers),
                    values=json.dumps(cells),
                    chunk_id=chunk_id,
                )
            )
            row_index += 1

        return rows

    def _extract_key_value_tables(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        rows: list[TableRow] = []
        current_headers: list[str] | None = None
        table_index = 0
        row_index = 0

        for raw_line in text.splitlines():
            line = self._normalize_spaces(self._strip_section_prefix(raw_line))
            if not line:
                current_headers = None
                row_index = 0
                continue

            record = self._parse_key_value_record(line)
            if len(record) < 2:
                continue

            headers = list(record.keys())
            values = list(record.values())
            if headers != current_headers:
                current_headers = headers
                row_index = 0
                table_index += 1

            rows.append(
                TableRow(
                    source_path=source_path,
                    table_id=f"{chunk_id}_kvtable_{table_index}",
                    row_index=row_index,
                    headers=json.dumps(headers),
                    values=json.dumps(values),
                    chunk_id=chunk_id,
                )
            )
            row_index += 1

        return rows

    def _extract_calibration_projection_table(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        lowered = text.lower()
        header_present = any(
            "date standard count" in self._normalize_spaces(line).lower()
            for line in text.splitlines()
        )
        if (
            "projected density" not in lowered
            and "calibration report" not in lowered
            and not header_present
        ):
            return []

        rows: list[TableRow] = []
        headers = ["Date", "Lower Limit Standard Count", "Upper Limit Standard Count"]
        row_index = 0
        for raw_line in text.splitlines():
            line = self._normalize_spaces(raw_line)
            match = self._CALIBRATION_ROW_RE.match(line)
            if not match:
                continue
            rows.append(
                TableRow(
                    source_path=source_path,
                    table_id=f"{chunk_id}_calibration_projection",
                    row_index=row_index,
                    headers=json.dumps(headers),
                    values=json.dumps(
                        [match.group("date"), match.group("lower"), match.group("upper")]
                    ),
                    chunk_id=chunk_id,
                )
            )
            row_index += 1

        return rows if len(rows) >= 2 else []

    def _extract_inventory_rows(
        self,
        text: str,
        chunk_id: str,
        source_path: str,
    ) -> list[TableRow]:
        rows: list[TableRow] = []
        in_table = False
        row_index = 0
        headers = ["Description", "Part Number", "Qty"]

        for raw_line in text.splitlines():
            line = self._normalize_spaces(raw_line)
            if not line:
                if rows:
                    break
                continue

            if not in_table:
                if self._INVENTORY_HEADER_RE.search(line):
                    in_table = True
                continue

            if line.lower().startswith("site:"):
                if rows:
                    break
                continue

            if line.lower().startswith("signs, spare"):
                continue

            match = self._TRAILING_QTY_RE.match(line)
            if not match:
                continue

            body = match.group("body").strip(" ,;-")
            qty = match.group("qty")
            part_number = ""
            part_match = self._PART_TOKEN_RE.search(body)
            if part_match:
                part_number = self._normalize_part_token(part_match.group(0))
                body = (body[: part_match.start()] + " " + body[part_match.end() :]).strip(" ,;-")

            description = body or line
            rows.append(
                TableRow(
                    source_path=source_path,
                    table_id=f"{chunk_id}_inventory_table",
                    row_index=row_index,
                    headers=json.dumps(headers),
                    values=json.dumps([description, part_number, qty]),
                    chunk_id=chunk_id,
                )
            )
            row_index += 1

        return rows if len(rows) >= 2 else []

    def _parse_key_value_record(self, line: str) -> dict[str, str]:
        matches = list(self._KEY_TOKEN_RE.finditer(line))
        if len(matches) < 2:
            return {}

        values_by_label: dict[str, str] = {}
        duplicate_counts: defaultdict[str, int] = defaultdict(int)

        for index, match in enumerate(matches):
            raw_label = self._clean_label(match.group("label"))
            if not raw_label:
                continue

            value_start = match.end()
            value_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            value = line[value_start:value_end].strip(" ,;\t")
            if not value:
                continue

            duplicate_counts[raw_label] += 1
            label = raw_label
            if duplicate_counts[raw_label] > 1:
                label = f"{raw_label} {duplicate_counts[raw_label]}"

            values_by_label[label] = value

        return values_by_label if len(values_by_label) >= 2 else {}

    def _merge_rows(self, rows: list[TableRow]) -> list[TableRow]:
        merged: dict[tuple[str, int, str], TableRow] = {}
        for row in rows:
            key = (row.table_id, row.row_index, row.values)
            merged[key] = row
        return list(merged.values())

    def _looks_like_pipe_row(self, line: str) -> bool:
        return line.startswith("|") and line.endswith("|") and line.count("|") >= 2

    def _is_markdown_separator(self, line: str) -> bool:
        if "|" not in line:
            return False
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        return bool(cells) and all(cells) and all(set(cell) <= {"-", ":"} for cell in cells)

    def _split_pipe_row(self, line: str) -> list[str]:
        return [cell.strip() for cell in line.strip("|").split("|")]

    def _looks_like_header_row(self, logical_row: int, cells: list[str]) -> bool:
        if logical_row == 1:
            return True

        header_tokens = {
            "po number",
            "po",
            "part number",
            "description",
            "qty",
            "quantity",
            "status",
            "ship date",
            "eta",
            "destination",
            "site",
            "requestor",
            "notes",
            "order date",
            "delivery date",
        }
        lowered = {cell.strip().lower() for cell in cells}
        return bool(lowered & header_tokens)

    def _clean_label(self, label: str) -> str:
        return self._normalize_spaces(label).strip(" ,;")

    def _normalize_spaces(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _normalize_part_token(self, token: str) -> str:
        cleaned = token.replace("‐", "-")
        cleaned = re.sub(r"\s*-\s*", "-", cleaned)
        return self._normalize_spaces(cleaned)

    def _strip_section_prefix(self, line: str) -> str:
        return re.sub(r"^\s*\[SECTION\]\s*", "", str(line or ""), flags=re.IGNORECASE)


def build_table_prompt_context(
    text: str,
    chunk_id: str,
    source_path: str,
    *,
    rows: list[TableRow] | None = None,
    max_rows: int = 5,
    max_value_pairs: int = 3,
    max_cell_chars: int = 48,
) -> TablePromptContext | None:
    """Build a compact synopsis + provenance block for table-ish chunks.

    This stays intentionally small for the first A/B lane: preserve row/header
    structure in the prompt without changing the canonical extraction schema.
    """
    extracted_rows = rows
    if extracted_rows is None:
        extracted_rows = DeterministicTableExtractor().extract(
            text=text,
            chunk_id=chunk_id,
            source_path=source_path,
        )
    if not extracted_rows:
        return None

    families = detect_logistics_table_families(source_path=source_path, text=text)
    header_signatures: list[str] = []
    seen_signatures: set[str] = set()
    row_provenance_lines: list[str] = []

    for row in extracted_rows:
        headers = _decode_json_list(row.headers)
        signature = _header_signature(headers)
        if signature not in seen_signatures:
            seen_signatures.add(signature)
            header_signatures.append(signature)

    for row in extracted_rows[:max_rows]:
        headers = _decode_json_list(row.headers)
        values = _decode_json_list(row.values)
        row_provenance_lines.append(
            (
                f"row_ref={row.table_id}:{row.row_index} "
                f"extractor={_extractor_name_from_table_id(row.table_id)} "
                f"headers={_header_signature(headers)} "
                f"values={_row_value_preview(headers, values, max_value_pairs, max_cell_chars)}"
            )
        )

    return TablePromptContext(
        table_mode=_infer_table_mode(extracted_rows),
        table_family=pick_primary_logistics_family(families),
        detected_row_count=len(extracted_rows),
        header_signatures=tuple(header_signatures[:3]),
        row_provenance_lines=tuple(row_provenance_lines),
    )


def _decode_json_list(raw: str) -> list[str]:
    """Support the tabular substrate workflow by handling the decode json list step."""
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return [str(raw or "")]
    if not isinstance(decoded, list):
        return [str(raw or "")]
    return [str(item) for item in decoded]


def _header_signature(headers: list[str]) -> str:
    """Support the tabular substrate workflow by handling the header signature step."""
    trimmed = [str(header).strip() for header in headers if str(header).strip()]
    if not trimmed:
        return "(no headers)"
    return " | ".join(trimmed[:6])


def _extractor_name_from_table_id(table_id: str) -> str:
    """Support the tabular substrate workflow by handling the extractor name from table id step."""
    if "_mdtable_" in table_id:
        return "markdown_table"
    if "_rowtable_" in table_id:
        return "bracket_rows"
    if "_pipekv_" in table_id:
        return "pipe_joined_kv"
    if "_kvtable_" in table_id:
        return "key_value"
    if table_id.endswith("_calibration_projection"):
        return "calibration_projection"
    if table_id.endswith("_inventory_table"):
        return "inventory_rows"
    return "deterministic_table"


def _infer_table_mode(rows: list[TableRow]) -> str:
    """Support the tabular substrate workflow by handling the infer table mode step."""
    if any(("_mdtable_" in row.table_id) or ("_rowtable_" in row.table_id) for row in rows):
        return "row_labeled"
    return "table_heavy"


def _row_value_preview(
    headers: list[str],
    values: list[str],
    max_pairs: int,
    max_cell_chars: int,
) -> str:
    """Support the tabular substrate workflow by handling the row value preview step."""
    pairs: list[str] = []
    for header, value in list(zip(headers, values))[:max_pairs]:
        pairs.append(f"{_truncate_cell(header, max_cell_chars)}={_truncate_cell(value, max_cell_chars)}")
    return "; ".join(pairs) if pairs else "(no values)"


def _truncate_cell(value: str, max_chars: int) -> str:
    """Support the tabular substrate workflow by handling the truncate cell step."""
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."
