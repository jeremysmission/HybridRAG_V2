"""Manual end-to-end smoke driver for the QA Workbench lanes.

Runs the highest-value proof surfaces without requiring a human to click
through the GUI:
  - launcher dry-run
  - aggregation self-check benchmark
  - count benchmark on the real audited target set
  - frozen regression fixture
  - optional Tk shell instantiation when a display is available
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2_ROOT))
SMOKE_OUTPUT_DIR = V2_ROOT / "tests" / "smoke_results" / "qa_workbench_2026-04-15"


def _run_cmd(args: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    """Support this test module by handling the run cmd step."""
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )


def _collect_runner_events(runner_cls, **kwargs) -> list[tuple[str, dict]]:
    """Support this test module by handling the collect runner events step."""
    events: list[tuple[str, dict]] = []
    done = threading.Event()

    def on_event(kind: str, payload: dict) -> None:
        events.append((kind, payload))
        if kind == "done":
            done.set()

    runner = runner_cls(on_event=on_event)
    runner.start(**kwargs)
    if not done.wait(timeout=180):
        raise RuntimeError(f"{runner_cls.__name__} did not emit terminal done")
    if runner._thread is not None:
        runner._thread.join(timeout=5)
    return events


def main() -> int:
    """Run this helper module directly from the command line."""
    summary: dict[str, object] = {
        "launcher_dry_run": None,
        "aggregation_self_check": None,
        "count_benchmark": None,
        "regression_fixture": None,
        "tk_shell": None,
    }
    SMOKE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["HYBRIDRAG_NO_PAUSE"] = "1"

    launcher = _run_cmd(
        ["cmd.exe", "/c", str(V2_ROOT / "start_qa_workbench.bat"), "--dry-run", "--debug-env"],
        cwd=V2_ROOT,
        env=env,
        timeout=120,
    )
    if launcher.returncode != 0:
        print(launcher.stdout)
        print(launcher.stderr, file=sys.stderr)
        raise SystemExit(2)
    summary["launcher_dry_run"] = {
        "ok": True,
        "headline": "HybridRAG V2 QA Workbench launcher -- dry run",
    }

    from src.gui.eval_panels.benchmark_runners import AggregationBenchmarkRunner, CountBenchmarkRunner
    from src.regression.schema_pattern import run_fixture
    from scripts.run_aggregation_benchmark_2026_04_15 import DEFAULT_MANIFEST
    from scripts import count_benchmark as cb

    aggregation_output = SMOKE_OUTPUT_DIR / "aggregation_self_check_2026-04-15.json"
    agg_events = _collect_runner_events(
        AggregationBenchmarkRunner,
        manifest_path=DEFAULT_MANIFEST,
        answers_path=None,
        output_path=aggregation_output,
        min_pass_rate=1.0,
    )
    agg_done = [payload for kind, payload in agg_events if kind == "done"][-1]
    if agg_done["status"] != "PASS":
        raise SystemExit(f"aggregation self-check failed: {agg_done}")
    agg_payload = json.loads(aggregation_output.read_text(encoding="utf-8"))
    summary["aggregation_self_check"] = {
        "ok": True,
        "pass_count": agg_payload["pass_count"],
        "total_items": agg_payload["total_items"],
        "output_json": str(aggregation_output),
    }

    count_events = _collect_runner_events(
        CountBenchmarkRunner,
        targets_path=cb.DEFAULT_TARGETS,
        lance_db=cb.DEFAULT_LANCE_DB,
        entity_db=cb.DEFAULT_ENTITY_DB,
        output_dir=SMOKE_OUTPUT_DIR,
        modes=cb.COUNT_MODES,
        include_deferred=False,
        predictions_json=None,
    )
    count_done = [payload for kind, payload in count_events if kind == "done"][-1]
    if count_done["status"] != "PASS":
        raise SystemExit(f"count benchmark failed: {count_done}")
    count_summary = count_done["summary"] or {}
    summary["count_benchmark"] = {
        "ok": True,
        "selected_targets": count_summary.get("selected_targets"),
        "expected_exact": count_summary.get("expected_exact"),
        "expected_total": count_summary.get("expected_total"),
        "output_json": (count_done["artifact_paths"] or {}).get("output_json"),
        "output_md": (count_done["artifact_paths"] or {}).get("output_md"),
    }

    report = run_fixture()
    if report.failed != 0:
        raise SystemExit(f"regression fixture failed: {report.failed} failures")
    summary["regression_fixture"] = {
        "ok": True,
        "fixture_id": report.fixture_id,
        "passed": report.passed,
        "total": report.total,
    }

    try:
        os.environ.setdefault("HYBRIDRAG_HEADLESS", "1")
        import tkinter as tk
        from src.gui.qa_workbench import QAWorkbench

        app = QAWorkbench()
        app.withdraw()
        app.update_idletasks()
        labels = [app._notebook.tab(tab_id, "text") for tab_id in app._notebook.tabs()]
        summary["tk_shell"] = {
            "ok": True,
            "tab_order": labels,
        }
        app.destroy()
    except Exception as exc:
        summary["tk_shell"] = {
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    summary_path = SMOKE_OUTPUT_DIR / f"qa_workbench_smoke_summary_{time.strftime('%Y%m%d_%H%M%S')}.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"summary_json={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
