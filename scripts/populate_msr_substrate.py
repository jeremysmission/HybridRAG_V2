"""Populate the Lane 3 MSR substrate from raw Site Visits corpus paths."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extraction.msr_extractor import extract_msr_records_from_path
from src.store.msr_substrate import MSRSubstrateStore


def _iter_candidate_visit_dirs(root: Path):
    for site_dir in root.iterdir():
        if not site_dir.is_dir():
            continue
        for visit_dir in site_dir.iterdir():
            if not visit_dir.is_dir():
                continue
            lowered = visit_dir.name.lower()
            if "asv" not in lowered and "rts" not in lowered:
                continue
            yield visit_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate MSR ASV/RTS substrate from raw corpus paths")
    parser.add_argument(
        "--raw-root",
        default=r"E:\CorpusTransfr\verified\IGS\! Site Visits\(01) Sites",
        help="Root folder to scan",
    )
    parser.add_argument(
        "--output-db",
        default=r"C:\HybridRAG_V2_Dev2\data_isolated\msr_substrate.sqlite3",
        help="SQLite output path",
    )
    args = parser.parse_args()

    root = Path(args.raw_root)
    store = MSRSubstrateStore(args.output_db)
    try:
        attempted = 0
        inserted = {"msr_asv": 0, "msr_rts": 0}
        for visit_dir in _iter_candidate_visit_dirs(root):
            records = extract_msr_records_from_path(str(visit_dir))
            if not records:
                continue
            attempted += len(records)
            delta = store.insert_many(records)
            inserted["msr_asv"] += delta["msr_asv"]
            inserted["msr_rts"] += delta["msr_rts"]
        summary = store.coverage_summary()
        print(
            f"[OK] MSR populate complete "
            f"(attempted={attempted}, inserted_asv={inserted['msr_asv']}, "
            f"inserted_rts={inserted['msr_rts']}, summary={summary})"
        )
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
