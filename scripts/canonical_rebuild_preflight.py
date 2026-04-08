"""
Sprint 13 preflight: validate a CorpusForge export before canonical rebuild.

Checks the export directory for completeness, schema compliance, and
consistency. Produces a pass/fail verdict and detailed report.

Usage:
    python scripts/canonical_rebuild_preflight.py --source C:/CorpusForge/data/export/export_YYYYMMDD_HHMM
    python scripts/canonical_rebuild_preflight.py --source path/to/export --output preflight_report.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from scripts.import_embedengine import (
    REQUIRED_CHUNK_FIELDS,
    resolve_export_dir,
    validate_chunks,
    validate_manifest,
)

DIVIDER = "=" * 55


def check_file_exists(export_dir: Path, filename: str) -> dict:
    """Check a file exists and return size info."""
    fpath = export_dir / filename
    if fpath.exists():
        size_mb = fpath.stat().st_size / (1024 * 1024)
        return {"file": filename, "exists": True, "size_mb": round(size_mb, 2)}
    return {"file": filename, "exists": False, "size_mb": 0}


def run_preflight(export_dir: Path) -> dict:
    """Run all preflight checks. Returns a report dict."""
    export_dir = resolve_export_dir(export_dir)
    report = {
        "export_dir": str(export_dir),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "checks": [],
        "verdict": "UNKNOWN",
    }

    errors = []
    warnings = []

    # --- Check 1: Required files exist ---
    required_files = ["chunks.jsonl", "vectors.npy"]
    optional_files = ["manifest.json", "skip_manifest.json"]

    file_checks = []
    for f in required_files:
        info = check_file_exists(export_dir, f)
        file_checks.append(info)
        if not info["exists"]:
            errors.append(f"MISSING required file: {f}")
    for f in optional_files:
        info = check_file_exists(export_dir, f)
        file_checks.append(info)
        if not info["exists"]:
            warnings.append(f"MISSING optional file: {f}")
    report["checks"].append({"name": "file_presence", "results": file_checks})

    # Bail early if required files missing
    if any(not fc["exists"] for fc in file_checks if fc["file"] in required_files):
        report["errors"] = errors
        report["warnings"] = warnings
        report["verdict"] = "FAIL"
        return report

    # --- Check 2: Load and count chunks ---
    chunks = []
    chunk_errors = 0
    chunks_path = export_dir / "chunks.jsonl"
    with open(chunks_path, encoding="utf-8-sig") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError as e:
                chunk_errors += 1
                if chunk_errors <= 5:
                    errors.append(f"JSON parse error on line {line_num}: {e}")

    if chunk_errors > 0:
        errors.append(f"Total JSON parse errors: {chunk_errors}")

    report["checks"].append({
        "name": "chunk_count",
        "total_lines": len(chunks) + chunk_errors,
        "valid_chunks": len(chunks),
        "parse_errors": chunk_errors,
    })

    # --- Check 3: Load vectors ---
    vectors_path = export_dir / "vectors.npy"
    try:
        vectors = np.load(str(vectors_path), mmap_mode="r")
        report["checks"].append({
            "name": "vectors",
            "shape": list(vectors.shape),
            "dtype": str(vectors.dtype),
        })
    except Exception as e:
        errors.append(f"Failed to load vectors.npy: {e}")
        report["checks"].append({"name": "vectors", "error": str(e)})
        report["errors"] = errors
        report["warnings"] = warnings
        report["verdict"] = "FAIL"
        return report

    # --- Check 4: Chunk/vector count alignment ---
    if vectors.shape[0] != len(chunks):
        errors.append(
            f"Chunk/vector count mismatch: {len(chunks)} chunks vs {vectors.shape[0]} vectors"
        )
    report["checks"].append({
        "name": "count_alignment",
        "chunks": len(chunks),
        "vectors": vectors.shape[0],
        "aligned": vectors.shape[0] == len(chunks),
    })

    # --- Check 5: Manifest validation ---
    manifest = {}
    manifest_path = export_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8-sig") as f:
            manifest = json.load(f)
    manifest_issues = validate_manifest(manifest, vectors)
    for issue in manifest_issues:
        if issue.startswith("REJECT"):
            errors.append(issue)
        else:
            warnings.append(issue)
    report["checks"].append({
        "name": "manifest_validation",
        "manifest_present": bool(manifest),
        "schema_version": manifest.get("schema_version"),
        "vector_dim": manifest.get("vector_dim"),
        "issues": manifest_issues,
    })

    # --- Check 6: Chunk field validation ---
    valid_chunks, rejected_chunks = validate_chunks(chunks)
    if rejected_chunks:
        warnings.append(f"{len(rejected_chunks)} chunks missing required fields")
    report["checks"].append({
        "name": "chunk_field_validation",
        "valid": len(valid_chunks),
        "rejected": len(rejected_chunks),
        "required_fields": list(REQUIRED_CHUNK_FIELDS),
    })

    # --- Check 7: Source file diversity ---
    source_files = {c.get("source_path", "") for c in valid_chunks}
    source_files.discard("")
    report["checks"].append({
        "name": "source_diversity",
        "unique_source_files": len(source_files),
        "chunks_per_file_avg": round(len(valid_chunks) / max(len(source_files), 1), 1),
    })

    # --- Check 8: Skip manifest ---
    skip_manifest_path = export_dir / "skip_manifest.json"
    if skip_manifest_path.exists():
        with open(skip_manifest_path, encoding="utf-8-sig") as f:
            skip_manifest = json.load(f)
        skipped = skip_manifest.get("skipped_files", [])
        deferred = skip_manifest.get("deferred_formats", [])
        report["checks"].append({
            "name": "skip_manifest",
            "skipped_files": len(skipped) if isinstance(skipped, list) else 0,
            "deferred_formats": len(deferred) if isinstance(deferred, list) else 0,
        })

    # --- Verdict ---
    report["errors"] = errors
    report["warnings"] = warnings
    if errors:
        report["verdict"] = "FAIL"
    elif warnings:
        report["verdict"] = "WARN"
    else:
        report["verdict"] = "PASS"

    return report


def print_report(report: dict) -> None:
    """Print a human-readable preflight report."""
    print(DIVIDER)
    print("  HybridRAG V2 -- Canonical Rebuild Preflight")
    print(DIVIDER)
    print(f"  Export: {report['export_dir']}")
    print(f"  Time:   {report['timestamp']}")
    print()

    for check in report["checks"]:
        name = check["name"]
        if name == "file_presence":
            for fc in check["results"]:
                status = "OK" if fc["exists"] else "MISSING"
                print(f"  [{status:7s}] {fc['file']:<25s} {fc['size_mb']:>8.1f} MB")
        elif name == "chunk_count":
            print(f"  Chunks:     {check['valid_chunks']:,} valid, {check['parse_errors']} parse errors")
        elif name == "vectors":
            if "error" in check:
                print(f"  Vectors:    ERROR -- {check['error']}")
            else:
                print(f"  Vectors:    {check['shape'][0]:,} x {check['shape'][1]}d ({check['dtype']})")
        elif name == "count_alignment":
            status = "ALIGNED" if check["aligned"] else "MISMATCH"
            print(f"  Alignment:  {status} ({check['chunks']:,} chunks, {check['vectors']:,} vectors)")
        elif name == "manifest_validation":
            if check["manifest_present"]:
                print(f"  Manifest:   schema_version={check['schema_version']}, vector_dim={check['vector_dim']}")
            else:
                print(f"  Manifest:   not present")
        elif name == "chunk_field_validation":
            print(f"  Fields:     {check['valid']:,} valid, {check['rejected']} rejected")
        elif name == "source_diversity":
            print(f"  Sources:    {check['unique_source_files']:,} files, ~{check['chunks_per_file_avg']} chunks/file")
        elif name == "skip_manifest":
            print(f"  Skipped:    {check['skipped_files']} files, {check['deferred_formats']} deferred formats")

    print()
    if report["errors"]:
        print("  ERRORS:")
        for e in report["errors"]:
            print(f"    - {e}")
    if report["warnings"]:
        print("  WARNINGS:")
        for w in report["warnings"]:
            print(f"    - {w}")

    print()
    verdict = report["verdict"]
    if verdict == "PASS":
        print(f"  VERDICT: PASS -- export is ready for canonical rebuild")
    elif verdict == "WARN":
        print(f"  VERDICT: WARN -- export usable but review warnings above")
    else:
        print(f"  VERDICT: FAIL -- do not proceed with import")
    print(DIVIDER)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preflight check for CorpusForge export before canonical rebuild."
    )
    parser.add_argument(
        "--source", required=True,
        help="Path to CorpusForge export directory.",
    )
    parser.add_argument(
        "--output", default=None,
        help="Write JSON report to this path (optional).",
    )
    parser.add_argument(
        "--fail-on-warn", action="store_true",
        help="Exit with code 1 on warnings (not just errors).",
    )
    args = parser.parse_args()

    export_dir = Path(args.source)
    report = run_preflight(export_dir)
    print_report(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  Report saved to: {out_path}")

    if report["verdict"] == "FAIL":
        sys.exit(1)
    if report["verdict"] == "WARN" and args.fail_on_warn:
        sys.exit(1)


if __name__ == "__main__":
    main()
