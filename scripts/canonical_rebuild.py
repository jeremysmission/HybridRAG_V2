"""
Sprint 13 canonical rebuild: orchestrate Forge export → V2 store rebuild.

Runs preflight validation, imports into a fresh LanceDB store, builds
indexes, and optionally runs golden eval to verify the rebuild.

Usage:
    python scripts/canonical_rebuild.py --source C:/CorpusForge/data/export/export_YYYYMMDD_HHMM
    python scripts/canonical_rebuild.py --source path/to/export --skip-eval
    python scripts/canonical_rebuild.py --source path/to/export --fresh-store data/index/lancedb_rebuild
"""

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

DIVIDER = "=" * 55


def run_step(step_name: str, func, *args, **kwargs):
    """Run a step with timing and status output."""
    print(f"\n  [{step_name}]")
    t0 = time.perf_counter()
    try:
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        print(f"  [{step_name}] DONE ({elapsed:.1f}s)")
        return result
    except SystemExit as e:
        elapsed = time.perf_counter() - t0
        print(f"  [{step_name}] FAILED ({elapsed:.1f}s)")
        raise
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"  [{step_name}] ERROR ({elapsed:.1f}s): {e}")
        raise


def step_preflight(source: Path) -> dict:
    """Run preflight validation."""
    from scripts.canonical_rebuild_preflight import run_preflight, print_report
    report = run_preflight(source)
    print_report(report)
    if report["verdict"] == "FAIL":
        print("  Preflight FAILED — aborting rebuild.", file=sys.stderr)
        sys.exit(1)
    return report


def step_backup_existing(lance_db_path: str) -> str | None:
    """Back up existing LanceDB store if it exists."""
    db_path = Path(lance_db_path)
    if not db_path.exists():
        print(f"  No existing store at {db_path} — skip backup")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.name}_backup_{timestamp}"
    print(f"  Backing up {db_path} → {backup_path}")
    shutil.copytree(str(db_path), str(backup_path))
    print(f"  Backup complete: {backup_path}")
    return str(backup_path)


def step_import(source: Path, config_path: str, strict: bool) -> dict:
    """Import Forge export into LanceDB store."""
    from scripts.import_embedengine import load_export, resolve_export_dir
    from src.config.schema import load_config
    from src.store.lance_store import LanceStore
    import logging
    import numpy as np

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

    export_dir = resolve_export_dir(source)
    chunks, vectors, manifest, skip_manifest = load_export(export_dir, strict=strict)

    config = load_config(config_path)
    store = LanceStore(config.paths.lance_db)
    before_count = store.count()

    print(f"  Importing {len(chunks):,} chunks into {config.paths.lance_db} ...")
    t0 = time.perf_counter()
    inserted = store.ingest_chunks(chunks, vectors)
    t_ingest = time.perf_counter() - t0

    print(f"  Building FTS index ...")
    store.create_fts_index()

    after_count = store.count()
    store.close()

    stats = {
        "before": before_count,
        "inserted": inserted,
        "duplicates": len(chunks) - inserted,
        "after": after_count,
        "ingest_seconds": round(t_ingest, 2),
        "rate_chunks_per_sec": round(inserted / max(t_ingest, 0.001)),
    }
    print(f"  Before: {before_count:,} | Inserted: {inserted:,} | After: {after_count:,}")
    print(f"  Rate: {stats['rate_chunks_per_sec']:,} chunks/sec")
    return stats


def step_vector_index(config_path: str) -> dict:
    """Build the vector index on the imported store."""
    from src.config.schema import load_config
    from src.store.lance_store import LanceStore

    config = load_config(config_path)
    store = LanceStore(config.paths.lance_db)
    count = store.count()

    if count < 1000:
        print(f"  Only {count:,} chunks — skipping vector index (< 1000 threshold)")
        store.close()
        return {"skipped": True, "reason": "below_threshold", "count": count}

    print(f"  Building IVF_PQ vector index on {count:,} chunks ...")
    result = store.create_vector_index(
        index_type="IVF_PQ",
        nprobes=20,
        optimize=True,
    )
    store.close()
    print(f"  Vector index: created={result.get('created', False)}")
    return result


def step_golden_eval() -> dict:
    """Run golden eval to verify rebuild quality."""
    import subprocess
    cmd = [
        str(V2_ROOT / ".venv" / "Scripts" / "python.exe"),
        str(V2_ROOT / "scripts" / "run_golden_eval.py"),
        "--retrieval-only",
    ]
    print(f"  Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(V2_ROOT))
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return {"returncode": proc.returncode}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonical rebuild: Forge export → V2 store → verify."
    )
    parser.add_argument(
        "--source", required=True,
        help="Path to CorpusForge export directory.",
    )
    parser.add_argument(
        "--config", default="config/config.yaml",
        help="V2 config path (default: config/config.yaml).",
    )
    parser.add_argument(
        "--skip-eval", action="store_true",
        help="Skip golden eval after import.",
    )
    parser.add_argument(
        "--skip-index", action="store_true",
        help="Skip vector index build after import.",
    )
    parser.add_argument(
        "--skip-backup", action="store_true",
        help="Skip backing up the existing store.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Strict mode — reject import on any chunk validation failure.",
    )
    args = parser.parse_args()

    source = Path(args.source)
    t_total_start = time.perf_counter()

    print(DIVIDER)
    print("  HybridRAG V2 — Canonical Rebuild")
    print(DIVIDER)
    print(f"  Source:  {source}")
    print(f"  Config:  {args.config}")
    print(f"  Strict:  {args.strict}")
    print(f"  Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 1: Preflight
    preflight = run_step("PREFLIGHT", step_preflight, source)

    # Step 2: Backup existing store
    backup_path = None
    if not args.skip_backup:
        from src.config.schema import load_config
        config = load_config(args.config)
        backup_path = run_step("BACKUP", step_backup_existing, config.paths.lance_db)

    # Step 3: Import
    import_stats = run_step("IMPORT", step_import, source, args.config, args.strict)

    # Step 4: Vector index
    index_result = {}
    if not args.skip_index:
        index_result = run_step("VECTOR INDEX", step_vector_index, args.config)

    # Step 5: Golden eval
    eval_result = {}
    if not args.skip_eval:
        eval_result = run_step("GOLDEN EVAL", step_golden_eval)

    t_total = time.perf_counter() - t_total_start

    # Summary
    print()
    print(DIVIDER)
    print("  REBUILD SUMMARY")
    print(DIVIDER)
    print(f"  Preflight:    {preflight['verdict']}")
    print(f"  Backup:       {backup_path or 'skipped'}")
    print(f"  Imported:     {import_stats['inserted']:,} chunks ({import_stats['rate_chunks_per_sec']:,} chunks/sec)")
    print(f"  Store total:  {import_stats['after']:,} chunks")
    if index_result:
        if index_result.get("skipped"):
            print(f"  Vector index: skipped ({index_result.get('reason', '')})")
        else:
            print(f"  Vector index: created={index_result.get('created', False)}")
    if eval_result:
        rc = eval_result.get("returncode", -1)
        print(f"  Golden eval:  {'PASS' if rc == 0 else 'FAIL (rc=' + str(rc) + ')'}")
    print(f"  Total time:   {t_total:.1f}s")
    print(DIVIDER)

    # Write rebuild report
    report_path = V2_ROOT / "tests" / "golden_eval" / "results" / f"rebuild_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "source": str(source),
            "preflight_verdict": preflight["verdict"],
            "import_stats": import_stats,
            "index_result": {k: v for k, v in index_result.items() if not callable(v)} if index_result else {},
            "eval_returncode": eval_result.get("returncode"),
            "total_seconds": round(t_total, 2),
        }, f, indent=2, default=str)
    print(f"  Report: {report_path}")


if __name__ == "__main__":
    main()
