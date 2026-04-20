"""
Raw-corpus-vs-substrate reconciliation.

Per Jeremy (2026-04-18): E:\\CorpusTransfr is the ground-truth 700GB raw source.
Counting files in the raw folder per (system, year, site) gives the upper bound
of what SHOULD be answerable. Comparing to counts in failure_events.db or
retrieval_metadata.sqlite3 tells us extraction loss.

Modes:
    --probe        count raw files matching patterns (fast recursive scan)
    --substrate    count rows in failure_events.db
    --compare      run both and emit a delta report
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections import Counter
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

logger = logging.getLogger("reconcile")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


SYSTEM_RE = re.compile(r"\b(nexion|isto)\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20[0-3]\d)\b")
SITE_RE = re.compile(
    r"\b(vandenberg|guam|learmonth|ascension|thule|eglin|alpena|fairford|wake|"
    r"hawaii|azores|okinawa|lualualei|curacao|djibouti|palau|kwajalein|niger|"
    r"american\s?samoa|misawa|diego\s?garcia|awase|pituffik|lemonnier)\b",
    re.IGNORECASE,
)


def probe_raw_corpus(raw_root: Path, *, limit: int | None = None) -> dict:
    """Recursively scan raw corpus; count files by (system, year, site)."""
    if not raw_root.exists():
        raise FileNotFoundError(f"Raw corpus root not found: {raw_root}")
    tallies: dict[str, Counter] = {
        "by_system": Counter(),
        "by_year": Counter(),
        "by_site": Counter(),
        "by_system_year": Counter(),
        "by_system_site_year": Counter(),
    }
    total = 0
    start = time.perf_counter()
    for path in raw_root.rglob("*"):
        if not path.is_file():
            continue
        total += 1
        if limit and total > limit:
            break
        if total % 50000 == 0:
            logger.info("Scanned %d files... (%.1fs)", total, time.perf_counter() - start)
        p = str(path).lower()
        sys_match = SYSTEM_RE.search(p)
        year_match = YEAR_RE.search(p)
        site_match = SITE_RE.search(p)
        system = sys_match.group(1).upper() if sys_match else ""
        year = int(year_match.group(1)) if year_match else None
        site = site_match.group(1).lower().replace(" ", "") if site_match else ""
        if site == "pituffik":
            site = "thule"
        if site == "lemonnier":
            site = "djibouti"
        if system:
            tallies["by_system"][system] += 1
        if year is not None:
            tallies["by_year"][year] += 1
        if site:
            tallies["by_site"][site] += 1
        if system and year is not None:
            tallies["by_system_year"][(system, year)] += 1
        if system and site and year is not None:
            tallies["by_system_site_year"][(system, site, year)] += 1
    elapsed = time.perf_counter() - start
    logger.info("Scanned %d files in %.1fs", total, elapsed)
    return {
        "total_files": total,
        "elapsed_sec": round(elapsed, 2),
        "by_system": dict(tallies["by_system"]),
        "by_year": dict(tallies["by_year"]),
        "by_site": dict(tallies["by_site"]),
        "by_system_year": {f"{s}|{y}": c for (s, y), c in tallies["by_system_year"].items()},
        "by_system_site_year": {
            f"{s}|{site}|{y}": c for (s, site, y), c in tallies["by_system_site_year"].items()
        },
    }


def count_substrate(lance_db_path: str | Path) -> dict:
    from src.store.failure_events_store import (
        FailureEventsStore, resolve_failure_events_db_path,
    )
    from src.store.retrieval_metadata_store import resolve_retrieval_metadata_db_path
    import sqlite3
    fe_db = resolve_failure_events_db_path(Path(lance_db_path).parent)
    out: dict = {"failure_events_db": str(fe_db)}
    if fe_db.exists():
        store = FailureEventsStore(fe_db)
        out["coverage"] = store.coverage_summary()
        # Per-system
        c = store._conn
        out["by_system"] = {
            r[0]: int(r[1]) for r in c.execute(
                "SELECT system, COUNT(*) FROM failure_events WHERE system!='' GROUP BY system"
            ).fetchall()
        }
        out["by_system_year"] = {
            f"{r[0]}|{r[1]}": int(r[2]) for r in c.execute(
                "SELECT system, event_year, COUNT(*) FROM failure_events "
                "WHERE system!='' AND event_year IS NOT NULL "
                "GROUP BY system, event_year ORDER BY 1, 2"
            ).fetchall()
        }
        store.close()
    meta_db = resolve_retrieval_metadata_db_path(lance_db_path)
    if meta_db.exists():
        conn = sqlite3.connect(str(meta_db))
        out["source_metadata_total"] = int(
            conn.execute("SELECT COUNT(*) FROM source_metadata").fetchone()[0] or 0
        )
        out["source_metadata_nexion"] = int(
            conn.execute("SELECT COUNT(*) FROM source_metadata WHERE lower(source_path) LIKE '%nexion%'").fetchone()[0] or 0
        )
        out["source_metadata_isto"] = int(
            conn.execute("SELECT COUNT(*) FROM source_metadata WHERE lower(source_path) LIKE '%isto%'").fetchone()[0] or 0
        )
        conn.close()
    return out


def compare(raw_root: Path, lance_db_path: str | Path) -> dict:
    raw = probe_raw_corpus(raw_root)
    sub = count_substrate(lance_db_path)
    delta: dict = {}
    raw_sys = raw.get("by_system", {})
    sub_sys = sub.get("by_system", {})
    for sysname in set(raw_sys) | set(sub_sys):
        r = int(raw_sys.get(sysname, 0))
        s = int(sub_sys.get(sysname, 0))
        delta[sysname] = {
            "raw_file_count": r,
            "substrate_event_count": s,
            "coverage_pct": round(100 * s / r, 2) if r else None,
        }
    return {
        "raw": raw,
        "substrate": sub,
        "delta_by_system": delta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile raw corpus vs failure_events substrate")
    parser.add_argument("--raw-root", default=r"E:\CorpusTransfr",
                        help="Raw corpus root (default: E:\\CorpusTransfr)")
    parser.add_argument("--lance-db", default="data/index/lancedb")
    parser.add_argument("--mode", choices=["probe", "substrate", "compare"], default="compare")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap raw-scan file count (useful for smoke test)")
    parser.add_argument("--output", default=None,
                        help="Write JSON report to this path")
    args = parser.parse_args()

    if args.mode == "probe":
        report = {"mode": "probe", "result": probe_raw_corpus(Path(args.raw_root), limit=args.limit)}
    elif args.mode == "substrate":
        report = {"mode": "substrate", "result": count_substrate(args.lance_db)}
    else:
        report = {
            "mode": "compare",
            "raw_root": str(args.raw_root),
            "lance_db": str(args.lance_db),
            "result": compare(Path(args.raw_root), args.lance_db),
        }

    txt = json.dumps(report, indent=2, default=str)
    print(txt)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(txt, encoding="utf-8")
        logger.info("Wrote report to %s", args.output)


if __name__ == "__main__":
    main()
