"""Lane 2 follow-on recon: count chunks per logistics family pattern.

Read-only. Pure SQL-style LIKE filters over the chunks table. No GPU,
no embedding calls, safe to run alongside a live production eval.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

V2_ROOT = Path(r"C:\HybridRAG_V2")
sys.path.insert(0, str(V2_ROOT))

from src.store.lance_store import LanceStore  # noqa: E402

LANCE_DIR = V2_ROOT / "data" / "index" / "lancedb"

PATTERNS: list[tuple[str, str]] = [
    ("packing_list_space",   "Packing List"),
    ("packing_list_nospace", "PackingList"),
    ("packing_slip",         "Packing Slip"),
    ("bom",                  "BOM"),
    ("bill_of_material",     "Bill of Material"),
    ("pr_and_po",            "PR & PO"),
    ("pr_po_nospace",        "PR&PO"),
    ("received",             "Received"),
    ("received_po",          "Received PO"),
    ("rcvd",                 "Rcvd"),
    ("space_report",         "Space Report"),
    ("dd250_space",          "DD 250"),
    ("dd250_nospace",        "DD250"),
    ("calibration",          "Calibration"),
    ("calibration_tracker",  "Calibration Tracker"),
    ("calib_short",          "Calib"),
    ("spare",                "Spare"),
    ("spares",               "Spares"),
    ("inventory",            "Inventory"),
    ("shipment",             "Shipment"),
    ("shipping",             "Shipping"),
    ("purchase_order",       "Purchase Order"),
    ("po_xls",               "PO.xls"),
    ("xlsx",                 ".xlsx"),
    ("xls",                  ".xls"),
    ("csv",                  ".csv"),
]


def escape_like(value: str) -> str:
    """Escape special characters so the value is safe to use in a query."""
    return value.replace("'", "''")


def main() -> None:
    """Parse command-line inputs and run the main lane2 family recon workflow."""
    store = LanceStore(str(LANCE_DIR))
    tbl = store._table
    if tbl is None:
        raise SystemExit("LanceDB chunks table missing")
    total = store.count()
    print(f"total chunks: {total:,}")

    rows: list[dict] = []
    for name, needle in PATTERNS:
        escaped = escape_like(needle)
        where = f"source_path LIKE '%{escaped}%'"
        try:
            reader = (
                tbl.search()
                .where(where)
                .select(["chunk_id"])
                .limit(total)
                .to_batches(100_000)
            )
            cnt = 0
            for batch in reader:
                cnt += batch.num_rows
            print(f"  {name:<24} ({needle!r:30}) -> {cnt:,}")
            rows.append({"name": name, "needle": needle, "count": cnt})
        except Exception as exc:
            print(f"  {name:<24} ({needle!r:30}) -> ERR {exc}")
            rows.append({"name": name, "needle": needle, "error": str(exc)})
    store.close()

    out = Path(r"C:\HybridRAG_V2\docs\lane2_family_recon_2026-04-13.json")
    out.write_text(
        json.dumps(
            {
                "total_chunks": total,
                "patterns": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
