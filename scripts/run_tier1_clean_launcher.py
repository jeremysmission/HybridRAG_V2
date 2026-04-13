#!/usr/bin/env python3
"""
Launcher for isolated full clean Tier 1 runs.

This wrapper is intentionally narrow:
- default to the clean Tier 1 config
- launch Tier 1 only
- tee stdout/stderr to a dated log file
- write a small run manifest for crash recovery

It does not change extraction semantics.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))
DEFAULT_CONFIG = V2_ROOT / "config" / "config.tier1_clean_2026-04-13.yaml"
DEFAULT_LOG_DIR = V2_ROOT / "logs" / "tier1_clean_runs"
TIER1_SCRIPT = V2_ROOT / "scripts" / "tiered_extract.py"


def utc_stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_id_stamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d_%H%M%S")


def resolve_path(raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = V2_ROOT / path
    return path.resolve()


def sibling_relationship_db(entity_db: Path) -> Path:
    return entity_db.with_name("relationships.sqlite3")


@dataclass(frozen=True)
class RunPlan:
    run_id: str
    config_path: str
    entity_db: str
    relationship_db: str
    lance_db: str
    log_path: str
    metadata_path: str
    command: list[str]


def build_run_plan(config_path: Path, log_dir: Path, run_id: str | None = None) -> RunPlan:
    from src.config.schema import load_config

    config = load_config(str(config_path))
    entity_db = resolve_path(config.paths.entity_db)
    lance_db = resolve_path(config.paths.lance_db)
    relationship_db = sibling_relationship_db(entity_db)

    actual_run_id = run_id or run_id_stamp()
    log_dir = resolve_path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"tier1_clean_run_{actual_run_id}.log"
    metadata_path = log_dir / f"tier1_clean_run_{actual_run_id}.json"

    command = [
        sys.executable,
        str(TIER1_SCRIPT),
        "--tier",
        "1",
        "--config",
        str(config_path),
    ]

    return RunPlan(
        run_id=actual_run_id,
        config_path=str(config_path),
        entity_db=str(entity_db),
        relationship_db=str(relationship_db),
        lance_db=str(lance_db),
        log_path=str(log_path),
        metadata_path=str(metadata_path),
        command=command,
    )


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp_path.replace(path)


def make_manifest(
    plan: RunPlan,
    *,
    status: str,
    launcher_pid: int,
    child_pid: int | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    return_code: int | None = None,
) -> dict:
    payload = asdict(plan)
    payload.update(
        {
            "status": status,
            "launcher_pid": launcher_pid,
            "child_pid": child_pid,
            "started_at": started_at,
            "finished_at": finished_at,
            "return_code": return_code,
            "v2_root": str(V2_ROOT),
            "launcher_python": sys.executable,
            "launcher_cwd": str(Path.cwd()),
        }
    )
    return payload


def emit(log_file, message: str) -> None:
    print(message, flush=True)
    log_file.write(message + "\n")
    log_file.flush()


def stream_child_output(proc: subprocess.Popen[str], log_file) -> int:
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
        log_file.write(line)
        log_file.flush()
    return proc.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch an isolated clean Tier 1 run with dated logs and a manifest."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG.relative_to(V2_ROOT)),
        help="Tier 1 clean config path. Defaults to config/config.tier1_clean_2026-04-13.yaml.",
    )
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR.relative_to(V2_ROOT)),
        help="Directory for dated launcher logs and run manifests.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional run id override (default: timestamp).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned launch and write the manifest, but do not start Tier 1.",
    )
    args = parser.parse_args(argv)

    config_path = resolve_path(args.config)
    log_dir = resolve_path(args.log_dir)
    plan = build_run_plan(config_path=config_path, log_dir=log_dir, run_id=args.run_id or None)

    started_at = utc_stamp()
    manifest_path = Path(plan.metadata_path)
    log_path = Path(plan.log_path)
    manifest = make_manifest(
        plan,
        status="planned" if args.dry_run else "running",
        launcher_pid=os.getpid(),
        started_at=started_at,
    )
    write_json_atomic(manifest_path, manifest)

    with log_path.open("a", encoding="utf-8", newline="\n") as log_file:
        emit(log_file, "=" * 78)
        emit(log_file, "TIER 1 CLEAN RUN LAUNCHER")
        emit(log_file, "=" * 78)
        emit(log_file, f"Run ID:          {plan.run_id}")
        emit(log_file, f"Started at:      {started_at}")
        emit(log_file, f"Config:          {plan.config_path}")
        emit(log_file, f"Target entity DB: {plan.entity_db}")
        emit(log_file, f"Target rel DB:    {plan.relationship_db}")
        emit(log_file, f"Target lance DB:  {plan.lance_db}")
        emit(log_file, f"Log file:         {plan.log_path}")
        emit(log_file, f"Manifest:         {plan.metadata_path}")
        emit(log_file, f"Launcher PID:     {os.getpid()}")
        emit(log_file, f"Python:           {sys.executable}")
        emit(log_file, f"Command:          {' '.join(plan.command)}")
        emit(log_file, "")

        if args.dry_run:
            emit(log_file, "DRY RUN — no Tier 1 process started.")
            manifest = make_manifest(
                plan,
                status="dry_run",
                launcher_pid=os.getpid(),
                started_at=started_at,
                finished_at=utc_stamp(),
                return_code=0,
            )
            write_json_atomic(manifest_path, manifest)
            return 0

        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        proc = subprocess.Popen(
            plan.command,
            cwd=str(V2_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        manifest = make_manifest(
            plan,
            status="running",
            launcher_pid=os.getpid(),
            child_pid=proc.pid,
            started_at=started_at,
        )
        write_json_atomic(manifest_path, manifest)
        emit(log_file, f"Child PID:        {proc.pid}")
        emit(log_file, "Launcher status:  streaming child output to console and log.")
        emit(log_file, "")

        t0 = time.perf_counter()
        try:
            return_code = stream_child_output(proc, log_file)
        except KeyboardInterrupt:
            proc.terminate()
            try:
                return_code = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                return_code = proc.wait()
            emit(log_file, "INTERRUPTED — child process terminated by launcher.")
        elapsed = time.perf_counter() - t0

        final_status = "completed" if return_code == 0 else "failed"
        emit(log_file, "")
        emit(log_file, f"FINAL STATUS: {final_status} (exit {return_code}, {elapsed:.1f}s)")
        emit(log_file, f"Finished at:   {utc_stamp()}")

        manifest = make_manifest(
            plan,
            status=final_status,
            launcher_pid=os.getpid(),
            child_pid=proc.pid,
            started_at=started_at,
            finished_at=utc_stamp(),
            return_code=return_code,
        )
        write_json_atomic(manifest_path, manifest)
        return int(return_code)


if __name__ == "__main__":
    raise SystemExit(main())
