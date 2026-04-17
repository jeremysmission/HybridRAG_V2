"""
Stage and optionally execute explicit CorpusForge -> HybridRAG V2 imports.

This script wraps import_embedengine.py with operator-visible staging artifacts:
  - deterministic source selection (explicit --source or --source-root --select latest)
  - preflight report copy
  - canary subset export (optional)
  - delta validation against the previous staged run
  - planned import command preview
  - durable stage result + ledger entry

Usage examples:
  python scripts/stage_forge_import.py --source C:/CorpusForge/data/production_output/export_20260409_0720 --mode dry-run
  python scripts/stage_forge_import.py --source-root C:/CorpusForge/data/production_output --select latest --canary-limit 2000 --mode dry-run
  python scripts/stage_forge_import.py --source-root C:/CorpusForge/data/production_output --select latest --mode import --create-index
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from scripts.canonical_rebuild_preflight import run_preflight
from scripts.import_embedengine import (
    apply_exclude_source_globs,
    load_export,
    resolve_export_dir,
    run_dry_run,
    run_import,
)


REQUIRED_EXPORT_FILES = ("chunks.jsonl", "vectors.npy")
DIVIDER = "=" * 70
PYTHON = str(V2_ROOT / ".venv" / "Scripts" / "python.exe")


def utc_now_iso() -> str:
    """Return ISO timestamp in local time for human-readable artifacts."""
    return datetime.now().isoformat(timespec="seconds")


def stage_timestamp() -> str:
    """Filesystem-friendly stage timestamp."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON with stable UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one JSON object per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run_tier1_extraction(config_path: str, *, limit: int = 0) -> dict[str, Any]:
    """Run Tier 1 extraction after import so staged imports populate relationships."""
    cmd = [
        PYTHON,
        "scripts/tiered_extract.py",
        "--tier",
        "1",
        "--config",
        config_path,
    ]
    if limit > 0:
        cmd.extend(["--limit", str(limit)])
    proc = subprocess.run(
        cmd,
        cwd=str(V2_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": cmd,
        "returncode": int(proc.returncode),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def has_required_export_files(export_dir: Path) -> bool:
    """Return True when the directory looks like a Forge export."""
    return all((export_dir / name).exists() for name in REQUIRED_EXPORT_FILES)


def _candidate_record(path: Path) -> dict[str, Any]:
    """Create a serializable metadata record for an export candidate."""
    stat = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "mtime_ns": stat.st_mtime_ns,
        "mtime_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def list_export_candidates(source_root: Path) -> list[Path]:
    """
    List candidate export directories under source_root.

    Deterministic ordering:
      1) newer directory modified time first
      2) lexical directory name descending as stable tie-breaker
    """
    candidates: list[Path] = []

    if source_root.is_dir() and has_required_export_files(source_root):
        candidates.append(source_root)

    if source_root.is_dir():
        for child in source_root.iterdir():
            if child.is_dir() and has_required_export_files(child):
                candidates.append(child)

    candidates.sort(key=lambda p: (p.stat().st_mtime_ns, p.name.lower()), reverse=True)
    return candidates


def select_latest_export(source_root: Path) -> tuple[Path, list[dict[str, Any]]]:
    """Select latest export from source_root with deterministic ordering."""
    candidates = list_export_candidates(source_root)
    if not candidates:
        raise FileNotFoundError(
            f"No export directories found under {source_root} with "
            f"{', '.join(REQUIRED_EXPORT_FILES)}."
        )
    candidate_records = [_candidate_record(p) for p in candidates]
    return candidates[0], candidate_records


def build_canary_export(
    parent_export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    skip_manifest: dict | None,
    canary_dir: Path,
    chunk_limit: int,
) -> tuple[Path, list[dict], np.ndarray, dict, dict | None]:
    """
    Build a deterministic canary export from the first N chunks/vectors.
    """
    if chunk_limit <= 0:
        raise ValueError("chunk_limit must be > 0")
    if chunk_limit > len(chunks):
        chunk_limit = len(chunks)

    canary_chunks = chunks[:chunk_limit]
    if isinstance(vectors, np.memmap):
        canary_vectors = np.array(vectors[:chunk_limit])
    else:
        canary_vectors = vectors[:chunk_limit]

    canary_dir.mkdir(parents=True, exist_ok=True)

    chunks_path = canary_dir / "chunks.jsonl"
    with open(chunks_path, "w", encoding="utf-8", newline="\n") as f:
        for chunk in canary_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    np.save(str(canary_dir / "vectors.npy"), canary_vectors)

    canary_manifest = dict(manifest or {})
    canary_manifest["chunk_count"] = len(canary_chunks)
    canary_manifest["vector_dim"] = int(canary_vectors.shape[1]) if canary_vectors.ndim == 2 else 0
    canary_manifest["canary_mode"] = True
    canary_manifest["canary_chunk_limit"] = int(chunk_limit)
    canary_manifest["canary_parent_export_dir"] = str(parent_export_dir)
    canary_manifest["canary_created_at"] = utc_now_iso()
    write_json(canary_dir / "manifest.json", canary_manifest)

    if skip_manifest is not None:
        write_json(canary_dir / "skip_manifest.json", skip_manifest)

    return canary_dir, canary_chunks, canary_vectors, canary_manifest, skip_manifest


def export_fingerprint(
    export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
) -> dict[str, Any]:
    """Create a compact fingerprint used for delta validation."""
    source_files = {c.get("source_path", "") for c in chunks}
    source_files.discard("")
    return {
        "export_dir": str(export_dir),
        "export_name": export_dir.name,
        "chunk_count": int(len(chunks)),
        "vector_count": int(vectors.shape[0]),
        "vector_dim": int(vectors.shape[1]) if vectors.ndim == 2 else 0,
        "source_file_count": int(len(source_files)),
        "embedding_model": (manifest or {}).get("embedding_model"),
        "manifest_timestamp": (manifest or {}).get("timestamp"),
    }


def load_last_ledger_entry(ledger_path: Path) -> dict[str, Any] | None:
    """Return the last valid JSON object from the ledger, if present."""
    if not ledger_path.exists():
        return None
    lines = ledger_path.read_text(encoding="utf-8-sig").splitlines()
    for line in reversed(lines):
        text = line.strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return None


def compute_delta(
    previous_fingerprint: dict[str, Any] | None,
    current_fingerprint: dict[str, Any],
) -> dict[str, Any]:
    """Compute operator-visible delta summary vs previous staged run."""
    if previous_fingerprint is None:
        return {
            "baseline": True,
            "message": "No previous staged run found. This run sets the baseline.",
            "previous_export_dir": None,
            "current_export_dir": current_fingerprint.get("export_dir"),
        }

    prev_chunks = int(previous_fingerprint.get("chunk_count", 0))
    curr_chunks = int(current_fingerprint.get("chunk_count", 0))
    prev_sources = int(previous_fingerprint.get("source_file_count", 0))
    curr_sources = int(current_fingerprint.get("source_file_count", 0))

    return {
        "baseline": False,
        "previous_export_dir": previous_fingerprint.get("export_dir"),
        "current_export_dir": current_fingerprint.get("export_dir"),
        "chunk_count_previous": prev_chunks,
        "chunk_count_current": curr_chunks,
        "chunk_count_delta": curr_chunks - prev_chunks,
        "source_files_previous": prev_sources,
        "source_files_current": curr_sources,
        "source_files_delta": curr_sources - prev_sources,
        "vector_dim_previous": previous_fingerprint.get("vector_dim"),
        "vector_dim_current": current_fingerprint.get("vector_dim"),
        "vector_dim_changed": previous_fingerprint.get("vector_dim") != current_fingerprint.get("vector_dim"),
        "embedding_model_previous": previous_fingerprint.get("embedding_model"),
        "embedding_model_current": current_fingerprint.get("embedding_model"),
        "embedding_model_changed": previous_fingerprint.get("embedding_model") != current_fingerprint.get("embedding_model"),
    }


def apply_visible_filters(
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    exclude_source_globs: list[str],
) -> tuple[list[dict], np.ndarray, dict]:
    """
    Apply explicit import-side source_path filters and annotate manifest.
    """
    if not exclude_source_globs:
        return chunks, vectors, manifest

    pre_filter_count = len(chunks)
    filtered_chunks, filtered_vectors, excluded = apply_exclude_source_globs(
        chunks, vectors, exclude_source_globs,
    )
    manifest = dict(manifest or {})
    manifest.setdefault("import_filters", {})
    manifest["import_filters"]["exclude_source_globs"] = list(exclude_source_globs)
    manifest["import_filters"]["pre_filter_chunk_count"] = pre_filter_count
    manifest["import_filters"]["post_filter_chunk_count"] = len(filtered_chunks)
    manifest["import_filters"]["excluded_chunk_count"] = excluded
    manifest["import_filters"]["filter_reason"] = "Operator-selected staging filter"
    manifest["import_filters"]["retire_when"] = "After source export no longer requires this import-side filter"
    return filtered_chunks, filtered_vectors, manifest


def command_preview(
    source_export: Path,
    args: argparse.Namespace,
) -> str:
    """Build explicit import command preview for operator visibility."""
    command: list[str] = [
        ".\\.venv\\Scripts\\python.exe",
        "scripts\\import_embedengine.py",
        "--source",
        str(source_export),
        "--config",
        str(args.config),
    ]
    if args.mode == "dry-run":
        command.append("--dry-run")
    if args.mode == "import" and args.create_index:
        command.append("--create-index")
    if args.index_type:
        command.extend(["--index-type", str(args.index_type)])
    if args.num_partitions is not None:
        command.extend(["--num-partitions", str(args.num_partitions)])
    if args.num_sub_vectors is not None:
        command.extend(["--num-sub-vectors", str(args.num_sub_vectors)])
    if args.nprobes is not None:
        command.extend(["--nprobes", str(args.nprobes)])
    if args.refine_factor is not None:
        command.extend(["--refine-factor", str(args.refine_factor)])
    if args.no_optimize_index:
        command.append("--no-optimize-index")
    if args.strict:
        command.append("--strict")
    for glob_pattern in args.exclude_source_glob:
        command.extend(["--exclude-source-glob", glob_pattern])
    return " ".join(command)


def resolve_source_selection(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    """Resolve source export and produce source-selection artifact payload."""
    if args.source:
        source = resolve_export_dir(Path(args.source))
        if not source.is_dir():
            raise FileNotFoundError(f"Source export directory not found: {source}")
        if not has_required_export_files(source):
            raise FileNotFoundError(
                f"Source {source} does not contain required files: {', '.join(REQUIRED_EXPORT_FILES)}"
            )
        return source, {
            "selection_mode": "explicit_source",
            "selected_export": str(source),
            "candidates": [_candidate_record(source)],
        }

    source_root = Path(args.source_root)
    if args.select != "latest":
        raise ValueError("--source-root requires explicit --select latest")
    selected, candidates = select_latest_export(source_root)
    return selected, {
        "selection_mode": "source_root_latest",
        "source_root": str(source_root),
        "selected_export": str(selected),
        "candidates": candidates,
    }


def main() -> None:
    """Parse command-line inputs and run the main stage forge import workflow."""
    parser = argparse.ArgumentParser(
        description="Stage and execute explicit Forge->V2 import workflows with durable artifacts."
    )
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument(
        "--source",
        default=None,
        help="Explicit export directory (or pointer file) to stage/import.",
    )
    src_group.add_argument(
        "--source-root",
        default=None,
        help="Root folder that contains export directories. Requires --select latest.",
    )
    parser.add_argument(
        "--select",
        choices=["latest"],
        default=None,
        help="Source-root selection mode. Must be explicit; no hidden defaults.",
    )
    parser.add_argument(
        "--mode",
        choices=["plan", "dry-run", "import"],
        default="dry-run",
        help="plan=stage artifacts only; dry-run=run import preview; import=write to LanceDB.",
    )
    parser.add_argument(
        "--stage-root",
        default="data/staging/import_runs",
        help="Directory where stage artifacts and ledger are written.",
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="V2 config path to pass to import logic.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Reject if any chunk fails required-field validation.",
    )
    parser.add_argument(
        "--canary-limit",
        type=int,
        default=0,
        help="If >0, stage/import only the first N chunks as a deterministic canary subset.",
    )
    parser.add_argument(
        "--create-index",
        action="store_true",
        help="Build vector index when --mode import is used.",
    )
    parser.add_argument(
        "--skip-tier1-after-import",
        action="store_true",
        help="Do not auto-run Tier 1 extraction after a successful staged import.",
    )
    parser.add_argument(
        "--index-type",
        default="IVF_PQ",
        help="Vector index type for --mode import (default: IVF_PQ).",
    )
    parser.add_argument("--num-partitions", type=int, default=None)
    parser.add_argument("--num-sub-vectors", type=int, default=None)
    parser.add_argument("--nprobes", type=int, default=20)
    parser.add_argument("--refine-factor", type=int, default=None)
    parser.add_argument(
        "--no-optimize-index",
        action="store_true",
        help="Skip index optimize/cleanup after index creation.",
    )
    parser.add_argument(
        "--exclude-source-glob",
        action="append",
        default=[],
        metavar="GLOB",
        help="Explicit import-side filter by source_path glob. Repeatable.",
    )
    args = parser.parse_args()

    try:
        selected_export, selection_payload = resolve_source_selection(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    stage_root = Path(args.stage_root)
    if not stage_root.is_absolute():
        stage_root = V2_ROOT / stage_root
    stage_id = f"stage_{stage_timestamp()}_{selected_export.name}"
    stage_dir = stage_root / stage_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = stage_root / "import_stage_ledger.jsonl"

    write_json(
        stage_dir / "source_selection.json",
        {
            "timestamp": utc_now_iso(),
            "stage_id": stage_id,
            **selection_payload,
        },
    )

    preflight_report = run_preflight(selected_export)
    write_json(stage_dir / "preflight_report.json", preflight_report)

    chunks: list[dict] = []
    vectors: np.ndarray = np.zeros((0, 0), dtype=np.float16)
    manifest: dict[str, Any] = {}
    skip_manifest: dict[str, Any] | None = None
    active_export_dir = selected_export
    active_scope = "full_export"

    if preflight_report.get("verdict") != "FAIL":
        chunks, vectors, manifest, skip_manifest = load_export(selected_export, strict=args.strict)
        chunks, vectors, manifest = apply_visible_filters(
            chunks, vectors, manifest, list(args.exclude_source_glob),
        )

        if args.canary_limit > 0:
            canary_dir = stage_dir / "canary_export"
            active_export_dir, chunks, vectors, manifest, skip_manifest = build_canary_export(
                selected_export,
                chunks,
                vectors,
                manifest,
                skip_manifest,
                canary_dir,
                args.canary_limit,
            )
            active_scope = f"canary_first_{len(chunks)}"

    current_fingerprint = export_fingerprint(active_export_dir, chunks, vectors, manifest) if chunks else {
        "export_dir": str(active_export_dir),
        "export_name": active_export_dir.name,
        "chunk_count": 0,
        "vector_count": 0,
        "vector_dim": 0,
        "source_file_count": 0,
        "embedding_model": None,
        "manifest_timestamp": None,
    }
    previous_entry = load_last_ledger_entry(ledger_path)
    previous_fingerprint = (previous_entry or {}).get("fingerprint")
    delta = compute_delta(previous_fingerprint, current_fingerprint)
    write_json(stage_dir / "delta_validation.json", delta)

    planned_command = command_preview(active_export_dir, args)
    (stage_dir / "planned_import_command.txt").write_text(planned_command + "\n", encoding="utf-8", newline="\n")

    mode_result: dict[str, Any] | None = None
    stage_status = "staged"

    if preflight_report.get("verdict") == "FAIL":
        stage_status = "blocked_preflight_fail"
    elif args.mode == "dry-run":
        mode_result = run_dry_run(
            active_export_dir, chunks, vectors, manifest, skip_manifest, args.config,
        )
        stage_status = "dry_run_complete"
    elif args.mode == "import":
        mode_result = run_import(
            active_export_dir,
            chunks,
            vectors,
            manifest,
            skip_manifest,
            args.config,
            args.create_index,
            args.index_type,
            args.num_partitions,
            args.num_sub_vectors,
            args.nprobes,
            args.refine_factor,
            not args.no_optimize_index,
        )
        if mode_result and not args.skip_tier1_after_import:
            tier1_limit = len(chunks) if args.canary_limit > 0 else 0
            tier1_result = run_tier1_extraction(args.config, limit=tier1_limit)
            mode_result["tier1_extraction"] = tier1_result
            stage_status = (
                "import_complete"
                if tier1_result["returncode"] == 0
                else "import_complete_tier1_failed"
            )
        else:
            stage_status = "import_complete"

    stage_result = {
        "stage_result_version": "1.0",
        "timestamp": utc_now_iso(),
        "stage_id": stage_id,
        "status": stage_status,
        "mode": args.mode,
        "scope": active_scope,
        "selected_export_dir": str(selected_export),
        "active_export_dir": str(active_export_dir),
        "preflight_verdict": preflight_report.get("verdict"),
        "config_path": str(args.config),
        "strict": bool(args.strict),
        "exclude_source_glob": list(args.exclude_source_glob),
        "canary_limit_requested": int(args.canary_limit),
        "fingerprint": current_fingerprint,
        "delta_validation": delta,
        "planned_command": planned_command,
        "mode_result": mode_result,
        "artifacts": {
            "source_selection": str(stage_dir / "source_selection.json"),
            "preflight_report": str(stage_dir / "preflight_report.json"),
            "delta_validation": str(stage_dir / "delta_validation.json"),
            "planned_command": str(stage_dir / "planned_import_command.txt"),
            "stage_result": str(stage_dir / "stage_result.json"),
        },
    }
    write_json(stage_dir / "stage_result.json", stage_result)

    ledger_entry = {
        "timestamp": utc_now_iso(),
        "stage_id": stage_id,
        "status": stage_status,
        "mode": args.mode,
        "selected_export_dir": str(selected_export),
        "active_export_dir": str(active_export_dir),
        "preflight_verdict": preflight_report.get("verdict"),
        "fingerprint": current_fingerprint,
        "mode_result": mode_result,
        "stage_result_path": str(stage_dir / "stage_result.json"),
    }
    append_jsonl(ledger_path, ledger_entry)

    print(DIVIDER)
    print("HybridRAG V2 -- Forge Import Staging")
    print(DIVIDER)
    print(f"stage_id:           {stage_id}")
    print(f"status:             {stage_status}")
    print(f"mode:               {args.mode}")
    print(f"selected export:    {selected_export}")
    print(f"active export:      {active_export_dir}")
    print(f"preflight verdict:  {preflight_report.get('verdict')}")
    print(f"scope:              {active_scope}")
    print(f"stage artifacts:    {stage_dir}")
    print(f"ledger:             {ledger_path}")
    print(DIVIDER)

    if preflight_report.get("verdict") == "FAIL":
        print("Preflight failed. Import execution was blocked.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
