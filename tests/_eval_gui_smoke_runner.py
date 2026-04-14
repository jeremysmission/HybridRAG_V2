"""Manual smoke driver for EvalRunner -- runs 3 real queries on GPU.

Not a pytest test. Invoked directly to prove the runner can:
  - boot the LanceStore
  - load the embedder on CUDA
  - run real queries through the production pipeline
  - stream events through the on_event callback
  - write a results JSON and markdown report
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

from src.gui.eval_panels.runner import EvalRunner  # noqa: E402


def main() -> int:
    events: list[tuple[str, dict]] = []
    done_evt = threading.Event()

    def on_event(kind: str, payload: dict) -> None:
        events.append((kind, payload))
        if kind == "log":
            print(f"[{payload.get('level','INFO'):5}] {payload.get('msg','')}")
        elif kind == "phase":
            print(f"[PHASE] {payload.get('phase')}")
        elif kind == "progress":
            print(f"[PROG ] {payload.get('current')}/{payload.get('total')}")
        elif kind == "query":
            print(
                f"[QUERY] {payload.get('query_id'):<8} "
                f"{payload.get('verdict'):<7} "
                f"route_ok={payload.get('routing_correct')} "
                f"{payload.get('embed_retrieve_ms')}ms"
            )
        elif kind == "scorecard":
            print(f"[SCORE] {payload}")
        elif kind == "done":
            print(f"[DONE ] {payload}")
            done_evt.set()

    runner = EvalRunner(on_event=on_event)
    runner.start(
        queries_path=V2_ROOT / "tests" / "golden_eval" / "production_queries_smoke3.json",
        config_path=V2_ROOT / "config" / "config.tier1_clean_2026-04-13.yaml",
        report_md=V2_ROOT / "docs" / "EVAL_GUI_SMOKE3_2026-04-13.md",
        results_json=V2_ROOT / "docs" / "eval_gui_smoke3_2026-04-13.json",
        gpu_index="0",
        max_queries=3,
    )

    if not done_evt.wait(timeout=600):
        print("[FAIL] runner did not emit 'done' within 600s")
        return 2
    runner._thread.join(timeout=5)

    done = [e for e in events if e[0] == "done"]
    if not done:
        print("[FAIL] no terminal done event")
        return 3
    status = done[0][1].get("status")
    if status != "PASS":
        print(f"[FAIL] runner status = {status}")
        return 4
    query_events = [e for e in events if e[0] == "query"]
    if len(query_events) != 3:
        print(f"[FAIL] expected 3 query events, got {len(query_events)}")
        return 5
    print(f"[OK] smoke passed: 3 queries, status={status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
