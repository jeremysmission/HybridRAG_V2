from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from scripts.run_tier1_clean_launcher import (
    DEFAULT_CONFIG,
    build_run_plan,
    make_manifest,
    main,
    run_id_stamp,
    write_json_atomic,
)


def test_run_id_stamp_uses_launcher_date():
    assert run_id_stamp(datetime(2026, 4, 13, 1, 2, 3)) == "20260413_010203"


def test_build_run_plan_uses_clean_config_and_dated_names(tmp_path):
    plan = build_run_plan(DEFAULT_CONFIG, tmp_path, run_id="20260413_123456")

    assert plan.config_path.endswith("config.tier1_clean_2026-04-13.yaml")
    assert plan.entity_db.endswith(r"data\index\clean\tier1_clean_20260413\entities.sqlite3")
    assert plan.relationship_db.endswith(r"data\index\clean\tier1_clean_20260413\relationships.sqlite3")
    assert plan.lance_db.endswith(r"data\index\lancedb")
    assert plan.log_path.endswith(r"tier1_clean_run_20260413_123456.log")
    assert plan.metadata_path.endswith(r"tier1_clean_run_20260413_123456.json")
    assert plan.command[1].endswith(r"scripts\tiered_extract.py")
    assert plan.command[-4:] == ["--tier", "1", "--config", str(DEFAULT_CONFIG)]


def test_make_manifest_tracks_targets_and_process_ids(tmp_path):
    plan = build_run_plan(DEFAULT_CONFIG, tmp_path, run_id="20260413_123456")
    manifest = make_manifest(
        plan,
        status="running",
        launcher_pid=1111,
        child_pid=2222,
        started_at="2026-04-13T08:30:00-06:00",
    )

    assert manifest["status"] == "running"
    assert manifest["launcher_pid"] == 1111
    assert manifest["child_pid"] == 2222
    assert manifest["entity_db"].endswith(r"tier1_clean_20260413\entities.sqlite3")
    assert manifest["relationship_db"].endswith(r"tier1_clean_20260413\relationships.sqlite3")
    assert manifest["lance_db"].endswith(r"data\index\lancedb")
    assert manifest["command"][0] == plan.command[0]

    out = tmp_path / "manifest.json"
    write_json_atomic(out, manifest)
    assert json.loads(out.read_text(encoding="utf-8"))["child_pid"] == 2222


def test_main_dry_run_writes_manifest_without_launch(tmp_path):
    log_dir = tmp_path / "tier1_clean_logs"
    rc = main(
        [
            "--dry-run",
            "--config",
            str(DEFAULT_CONFIG),
            "--log-dir",
            str(log_dir),
            "--run-id",
            "20260413_123456",
        ]
    )

    assert rc == 0
    log_path = log_dir / "tier1_clean_run_20260413_123456.log"
    metadata_path = log_dir / "tier1_clean_run_20260413_123456.json"
    assert log_path.exists()
    assert metadata_path.exists()

    manifest = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "dry_run"
    assert manifest["return_code"] == 0
    assert manifest["child_pid"] is None
    assert "DRY RUN" in log_path.read_text(encoding="utf-8")
