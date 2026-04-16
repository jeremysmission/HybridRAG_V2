"""Lane 2 follow-on sampler: dump first N chunk texts per logistics family.

Read-only. Pulls small samples so we can see the actual text shape of real
corpus chunks before deciding which deterministic extractor to write.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

V2_ROOT = Path(r"C:\HybridRAG_V2")
sys.path.insert(0, str(V2_ROOT))

from src.store.lance_store import LanceStore  # noqa: E402

LANCE_DIR = V2_ROOT / "data" / "index" / "lancedb"

SAMPLE_PER_FAMILY = 4
MAX_TEXT_LEN = 1800

FAMILIES: list[tuple[str, str]] = [
    ("packing_list", "Packing List"),
    ("packing_slip", "Packing Slip"),
    ("pr_and_po",    "PR & PO"),
    ("rcvd",         "Rcvd"),
    ("received",     "Received"),
    ("space_report", "Space Report"),
    ("shipment",     "Shipment"),
    ("calibration",  "Calibration"),
    ("spares",       "Spares"),
    ("dd250",        "DD250"),
    ("po_xls",       "PO.xls"),
]


def escape_like(value: str) -> str:
    """Escape special characters so the value is safe to use in a query."""
    return value.replace("'", "''")


def main() -> None:
    """Parse command-line inputs and run the main lane2 family sampler workflow."""
    store = LanceStore(str(LANCE_DIR))
    tbl = store._table
    total = store.count()
    out: dict[str, object] = {"total_chunks": total, "families": {}}

    for name, needle in FAMILIES:
        escaped = escape_like(needle)
        where = f"source_path LIKE '%{escaped}%'"
        try:
            result = (
                tbl.search()
                .where(where)
                .select(["chunk_id", "source_path", "text"])
                .limit(SAMPLE_PER_FAMILY)
                .to_arrow()
            )
            samples = []
            for i in range(result.num_rows):
                samples.append({
                    "chunk_id": str(result.column("chunk_id")[i]),
                    "source_path": str(result.column("source_path")[i]),
                    "text": str(result.column("text")[i])[:MAX_TEXT_LEN],
                })
            out["families"][name] = {
                "needle": needle,
                "sampled": len(samples),
                "samples": samples,
            }
            print(f"{name:<16} sampled {len(samples)} for needle {needle!r}")
        except Exception as exc:
            out["families"][name] = {"needle": needle, "error": str(exc)}
            print(f"{name:<16} ERR {exc}")

    store.close()

    out_path = V2_ROOT / "docs" / "lane2_family_samples_2026-04-13.json"
    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
