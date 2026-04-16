"""
Walk-away script: Import CorpusForge export + run Tier 1+2 extraction in one shot.

Plug in the E: drive (or point --source at a local copy), run this, walk away.
It chains: import → Tier 1 regex → Tier 2 GLiNER → done.

Usage:
    .venv\\Scripts\\python.exe scripts/run_full_import_and_extract.py --source E:/CorpusIndexEmbeddingsOnly/export_20260411_0720
    .venv\\Scripts\\python.exe scripts/run_full_import_and_extract.py --source E:/CorpusIndexEmbeddingsOnly/export_20260411_0720 --tier 1
    .venv\\Scripts\\python.exe scripts/run_full_import_and_extract.py --source C:/HybridRAG_V2/data/forge_exports --skip-import

Time estimates (10.4M chunks):
    Import + index build:  ~25-40 min
    Tier 1 regex:          ~30-60 min
    Tier 2 GLiNER (GPU):   ~1-4 hours depending on GPU
    Total:                 ~2-5 hours unattended
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
PYTHON = str(V2_ROOT / ".venv" / "Scripts" / "python.exe")
DIVIDER = "=" * 60


def log(msg: str) -> None:
    """Support the run full import and extract workflow by handling the log step."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def run_step(name: str, cmd: list[str], timeout: int = 0) -> int:
    """Run a subprocess step with live output. Returns exit code."""
    log(f"START: {name}")
    log(f"  Command: {' '.join(cmd)}")
    t0 = time.perf_counter()

    kwargs = dict(cwd=str(V2_ROOT), text=True, bufsize=1)
    if timeout > 0:
        kwargs["timeout"] = timeout

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
        for line in proc.stdout:
            print(f"  | {line}", end="", flush=True)
        proc.wait()
        elapsed = time.perf_counter() - t0
        if proc.returncode == 0:
            log(f"DONE: {name} ({elapsed:.1f}s)")
        else:
            log(f"FAILED: {name} (exit code {proc.returncode}, {elapsed:.1f}s)")
        return proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        log(f"TIMEOUT: {name} after {timeout}s")
        return -1
    except Exception as e:
        log(f"ERROR: {name} — {e}")
        return -1


def main() -> int:
    """Parse command-line inputs and run the main run full import and extract workflow."""
    parser = argparse.ArgumentParser(
        description="Walk-away: import CorpusForge export + run tiered extraction."
    )
    parser.add_argument(
        "--source", required=True,
        help="Path to CorpusForge export directory (contains chunks.jsonl + vectors.npy).",
    )
    parser.add_argument(
        "--tier", type=int, default=2, choices=[1, 2],
        help="Max extraction tier (1=regex only, 2=regex+GLiNER). Default: 2.",
    )
    parser.add_argument(
        "--config", default="config/config.yaml",
        help="V2 config file path.",
    )
    parser.add_argument(
        "--skip-import", action="store_true",
        help="Skip the import step (use if LanceDB is already populated).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate source and print plan without executing.",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    chunks_path = source / "chunks.jsonl"
    vectors_path = source / "vectors.npy"
    manifest_path = source / "manifest.json"

    print(DIVIDER)
    print("  HybridRAG V2 — Walk-Away Import + Extraction")
    print(DIVIDER)
    log(f"Source:      {source}")
    log(f"Config:      {args.config}")
    log(f"Max tier:    {args.tier}")
    log(f"Skip import: {args.skip_import}")
    log(f"Python:      {PYTHON}")

    # GPU pre-check for Tier 2
    if args.tier >= 2:
        try:
            import torch
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                for i in range(gpu_count):
                    free, total = torch.cuda.mem_get_info(i)
                    log(f"GPU {i}:       {torch.cuda.get_device_name(i)} — {free/1e9:.1f}GB free / {total/1e9:.1f}GB total")
            else:
                log("WARNING: CUDA not available. Tier 2 GLiNER will abort (CPU is too slow).")
        except ImportError:
            log("WARNING: torch not importable. GPU status unknown.")
    print()

    # Validate source exists
    missing = []
    if not args.skip_import:
        for f in [chunks_path, vectors_path, manifest_path]:
            if not f.exists():
                missing.append(str(f))
        if missing:
            log(f"ABORT: Missing source files: {missing}")
            return 2

        # Print manifest summary
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            chunk_count = manifest.get("chunk_count", "unknown")
            vector_dim = manifest.get("vector_dim", "unknown")
            model = manifest.get("embedding_model", "unknown")
            log(f"Manifest:    {chunk_count:,} chunks, dim={vector_dim}, model={model}")
        except Exception as e:
            log(f"WARNING: Could not read manifest: {e}")

    if args.dry_run:
        log("DRY RUN — would execute:")
        if not args.skip_import:
            log(f"  1. Import {source} into LanceDB with --create-index")
        log(f"  2. Tier 1 regex extraction (all chunks)")
        if args.tier >= 2:
            log(f"  3. Tier 2 GLiNER extraction (filtered subset, GPU)")
        log("Exiting without changes.")
        return 0

    results = {}
    overall_start = time.perf_counter()

    # Step 1: Import
    if not args.skip_import:
        rc = run_step(
            "Import CorpusForge export into LanceDB",
            [PYTHON, "scripts/import_embedengine.py",
             "--source", str(source),
             "--create-index"],
        )
        results["import"] = rc
        if rc != 0:
            log("ABORT: Import failed. Not proceeding to extraction.")
            return 2
        print()

    # Step 2: Tier 1 regex extraction
    rc = run_step(
        "Tier 1 regex extraction",
        [PYTHON, "scripts/tiered_extract.py",
         "--tier", "1",
         "--config", args.config],
    )
    results["tier1"] = rc
    if rc != 0:
        log("WARNING: Tier 1 failed. Proceeding to Tier 2 anyway (may still extract).")
    print()

    # Step 3: Tier 2 GLiNER (if requested)
    if args.tier >= 2:
        rc = run_step(
            "Tier 2 GLiNER extraction (GPU)",
            [PYTHON, "scripts/tiered_extract.py",
             "--tier", "2",
             "--config", args.config],
        )
        results["tier2"] = rc
        print()

    # Summary
    total_elapsed = time.perf_counter() - overall_start
    hours = int(total_elapsed // 3600)
    minutes = int((total_elapsed % 3600) // 60)

    print()
    print(DIVIDER)
    log(f"COMPLETE — total wall time: {hours}h {minutes}m")
    for step, rc in results.items():
        status = "PASS" if rc == 0 else f"FAILED (exit {rc})"
        log(f"  {step}: {status}")
    print(DIVIDER)

    if any(rc != 0 for rc in results.values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
