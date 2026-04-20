#!/usr/bin/env python3
"""Live QA harness for the real HybridRAG main query panel.

This harness targets the actual `HybridRAGApp` / `src.gui.launch_gui`
surface, not the QA Workbench. It boots the real app, waits for Ask
readiness, runs live semantic and aggregation queries, and fails hard on
missing widgets, wrong query path/tier, footnote wiring regressions, or Tk
callback exceptions.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import tkinter as tk


PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug_now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@dataclass
class CheckResult:
    check_id: str
    passed: bool
    detail: str
    duration_ms: float
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class HarnessReport:
    tool: str = "tools/qa/query_panel_live_harness.py"
    mode: str = "real"
    started_utc: str = ""
    finished_utc: str = ""
    boot_ready_seconds: float | None = None
    verdict: str = "FAIL"
    checks: list[CheckResult] = field(default_factory=list)
    callback_errors: list[dict[str, str]] = field(default_factory=list)
    thread_errors: list[dict[str, str]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)


class HarnessFailure(RuntimeError):
    """Raised when a required QA check fails."""


class HarnessLogger:
    """Dual sink logger for stdout-style evidence and a text artifact."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._lines: list[str] = []

    def log(self, message: str) -> None:
        stamped = f"[{time.strftime('%H:%M:%S')}] {message}"
        self._lines.append(stamped)
        print(stamped, flush=True)

    def write(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if self.log_path.exists():
            existing = self.log_path.read_text(encoding="utf-8")
            if existing and not existing.endswith("\n"):
                existing += "\n"
        combined = existing + "\n".join(self._lines) + "\n"
        self.log_path.write_text(combined, encoding="utf-8")


def _pump(app: tk.Tk, seconds: float = 0.05) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            app.update_idletasks()
            app.update()
        except tk.TclError:
            break
        time.sleep(0.01)


def _wait_until(
    app: tk.Tk,
    predicate: Callable[[], Any],
    timeout_s: float,
    description: str,
) -> Any:
    deadline = time.time() + timeout_s
    last_exc: Exception | None = None
    while time.time() < deadline:
        _pump(app, 0.05)
        try:
            result = predicate()
            if result:
                return result
        except Exception as exc:  # pragma: no cover - debugging aid
            last_exc = exc
        time.sleep(0.05)
    if last_exc is not None:
        raise HarnessFailure(f"{description} timed out after {timeout_s:.1f}s ({last_exc})")
    raise HarnessFailure(f"{description} timed out after {timeout_s:.1f}s")


def _install_tk_error_trap(app: tk.Tk) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    def _capture(exc_type, exc_value, exc_tb) -> None:
        errors.append(
            {
                "error": str(exc_value),
                "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
            }
        )

    app.report_callback_exception = _capture
    return errors


def _install_thread_error_trap() -> tuple[list[dict[str, str]], Any]:
    errors: list[dict[str, str]] = []
    original = threading.excepthook

    def _capture(args) -> None:
        errors.append(
            {
                "error": str(args.exc_value),
                "thread": getattr(args.thread, "name", "unknown"),
                "traceback": "".join(
                    traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
                ),
            }
        )
        original(args)

    threading.excepthook = _capture
    return errors, original


def _restore_thread_error_trap(original) -> None:
    threading.excepthook = original


def _mapped(widget: tk.Widget) -> bool:
    return bool(widget.winfo_ismapped())


def _managed(widget: tk.Widget) -> bool:
    try:
        return bool(widget.winfo_manager())
    except Exception:
        return False


def _visible_snapshot(qp) -> dict[str, bool]:
    return {
        "question_entry": _mapped(qp.question_entry),
        "ask_btn": _mapped(qp.ask_btn),
        "stop_btn": _mapped(qp.stop_btn),
        "answer_text": _mapped(qp.answer_text),
        "sources_toggle": _mapped(qp._sources_toggle_btn),
        "metrics_line": _mapped(qp._metrics_label),
    }


def _widget_text(widget: tk.Widget) -> str:
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def _find_widgets_by_text(root: tk.Widget, text: str) -> list[tk.Widget]:
    matches: list[tk.Widget] = []
    for child in root.winfo_children():
        if _widget_text(child) == text:
            matches.append(child)
        matches.extend(_find_widgets_by_text(child, text))
    return matches


def _first_widget_by_text(root: tk.Widget, text: str) -> tk.Widget:
    matches = _find_widgets_by_text(root, text)
    if not matches:
        raise HarnessFailure(f"Missing widget with text {text!r}")
    return matches[0]


def _collect_card(widget_container: tk.Widget, display_num: int) -> tk.Widget:
    for child in widget_container.winfo_children():
        if getattr(child, "_source_index", None) == display_num:
            return child
    raise HarnessFailure(f"Missing source card for footnote [{display_num}]")


def _run_check(
    report: HarnessReport,
    harness_log: HarnessLogger,
    check_id: str,
    func: Callable[[], dict[str, Any] | None],
) -> None:
    start = time.perf_counter()
    try:
        data = func() or {}
        duration_ms = (time.perf_counter() - start) * 1000
        report.checks.append(
            CheckResult(
                check_id=check_id,
                passed=True,
                detail="PASS",
                duration_ms=duration_ms,
                data=data,
            )
        )
        harness_log.log(f"PASS {check_id} {json.dumps(data, default=str, sort_keys=True)}")
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        report.checks.append(
            CheckResult(
                check_id=check_id,
                passed=False,
                detail=str(exc),
                duration_ms=duration_ms,
                data={"traceback": traceback.format_exc()},
            )
        )
        raise


def _create_real_app(logger: logging.Logger, visible: bool) -> tuple[tk.Tk, Any, threading.Thread]:
    from src.config.schema import load_config
    from src.gui.app import HybridRAGApp
    from src.gui.model import GUIModel
    from src.gui import launch_gui

    launch_gui._sanitize_tk_env()
    config = load_config(str(PROJECT_ROOT / "config" / "config.yaml"))
    placeholder_model = GUIModel(config=config)
    app = HybridRAGApp(model=placeholder_model, config=config)
    if not visible:
        app.withdraw()
    backend_thread = threading.Thread(
        target=launch_gui._load_backends,
        args=(app, placeholder_model, config, logger),
        daemon=True,
        name="query-panel-live-harness-backend",
    )
    backend_thread.start()
    return app, config, backend_thread


def _wait_for_ready(app: tk.Tk, harness_log: HarnessLogger) -> float:
    qp = app.query_panel
    start = time.time()

    def _ready() -> bool:
        model = getattr(qp, "_model", None)
        if model is None or model.pipeline is None:
            return False
        return str(qp.ask_btn.cget("state")) == tk.NORMAL

    _wait_until(app, _ready, 180.0, "Ask readiness")
    ready_s = time.time() - start
    harness_log.log(
        "READY ask_state={} stop_state={} pipeline={} boot_ready_seconds={:.2f}".format(
            qp.ask_btn.cget("state"),
            qp.stop_btn.cget("state"),
            type(qp._model.pipeline).__name__,
            ready_s,
        )
    )
    return ready_s


def _check_default_view(app: tk.Tk) -> dict[str, Any]:
    qp = app.query_panel
    topk_label = _first_widget_by_text(qp._admin_frame, "Top-K:")
    candidate_label = _first_widget_by_text(qp._admin_frame, "Candidate Pool:")
    min_score_label = _first_widget_by_text(qp._admin_frame, "Min Score:")
    reranker_label = _first_widget_by_text(qp._admin_frame, "Reranker Top-N:")
    reranker_enabled = _first_widget_by_text(qp._admin_frame, "Reranker Enabled")
    grounded_only = _first_widget_by_text(qp._admin_frame, "Grounded Only")

    consecutive = 0
    last_visible = _visible_snapshot(qp)
    deadline = time.time() + 5.0
    while time.time() < deadline:
        _pump(app, 0.10)
        visible = _visible_snapshot(qp)
        last_visible = visible
        if all(visible.values()):
            consecutive += 1
            if consecutive >= 3:
                break
        else:
            consecutive = 0
    required_visible = last_visible
    required_hidden = {
        "admin_frame": _mapped(qp._admin_frame),
        "ibit_label": _mapped(qp._ibit_label),
        "endpoint_combo": _mapped(qp._endpoint_combo),
        "topk_label": _mapped(topk_label),
        "candidate_pool": _mapped(candidate_label),
        "min_score": _mapped(min_score_label),
        "reranker_topn": _mapped(reranker_label),
        "reranker_enabled": _mapped(reranker_enabled),
        "grounded_only": _mapped(grounded_only),
        "path_badge": _mapped(qp._path_badge),
        "confidence_badge": _mapped(qp._confidence_badge),
        "evidence_badge": _mapped(qp._evidence_badge),
    }

    hidden_failures = [k for k, v in required_hidden.items() if v]
    visible_failures = [k for k, v in required_visible.items() if not v]
    if not all(required_visible.values()) or visible_failures or hidden_failures:
        raise HarnessFailure(
            f"default view mismatch visible_missing={visible_failures} hidden_not_hidden={hidden_failures}"
        )

    return {"visible": required_visible, "hidden": required_hidden}


def _check_admin_toggle(app: tk.Tk) -> dict[str, Any]:
    qp = app.query_panel
    topk_label = _first_widget_by_text(qp._admin_frame, "Top-K:")
    candidate_label = _first_widget_by_text(qp._admin_frame, "Candidate Pool:")
    min_score_label = _first_widget_by_text(qp._admin_frame, "Min Score:")
    reranker_label = _first_widget_by_text(qp._admin_frame, "Reranker Top-N:")
    reranker_enabled = _first_widget_by_text(qp._admin_frame, "Reranker Enabled")
    grounded_only = _first_widget_by_text(qp._admin_frame, "Grounded Only")

    qp._admin_toggle.invoke()
    _pump(app, 0.20)
    opened = {
        "admin_frame": _mapped(qp._admin_frame),
        "ibit_label": _managed(qp._ibit_label),
        "endpoint_combo": _managed(qp._endpoint_combo),
        "topk_label": _managed(topk_label),
        "candidate_pool": _managed(candidate_label),
        "min_score": _managed(min_score_label),
        "reranker_topn": _managed(reranker_label),
        "reranker_enabled": _managed(reranker_enabled),
        "grounded_only": _managed(grounded_only),
        "path_badge": _managed(qp._path_badge),
        "confidence_badge": _managed(qp._confidence_badge),
        "evidence_badge": _managed(qp._evidence_badge),
        "toggle_text": _widget_text(qp._admin_toggle),
    }
    if not all(v for k, v in opened.items() if k != "toggle_text"):
        bad = [k for k, v in opened.items() if k != "toggle_text" and not v]
        raise HarnessFailure(f"admin open missing widgets: {bad}")

    qp._admin_toggle.invoke()
    _pump(app, 0.20)
    closed = {
        "admin_frame": _mapped(qp._admin_frame),
        "toggle_text": _widget_text(qp._admin_toggle),
    }
    if closed["admin_frame"]:
        raise HarnessFailure("admin frame stayed visible after closing")

    return {"opened": opened, "closed": closed}


def _submit_query(app: tk.Tk, question: str) -> Any:
    qp = app.query_panel
    previous = qp._last_response
    qp.question_entry.delete(0, tk.END)
    qp.question_entry.insert(0, question)
    qp.ask_btn.invoke()
    _wait_until(
        app,
        lambda: getattr(qp._model, "is_querying", False) or str(qp.stop_btn.cget("state")) == tk.NORMAL,
        15.0,
        f"query start {question!r}",
    )
    _wait_until(
        app,
        lambda: (qp._last_response is not previous) and (not qp._model.is_querying),
        120.0,
        f"query completion {question!r}",
    )
    _pump(app, 0.25)
    return qp._last_response


def _first_footnote_tag(qp) -> tuple[str, int]:
    tag_names = [name for name in qp.answer_text.tag_names() if name.startswith("fn_d")]
    with_ranges = []
    for tag in tag_names:
        ranges = qp.answer_text.tag_ranges(tag)
        if ranges:
            with_ranges.append(tag)
    if not with_ranges:
        raise HarnessFailure("semantic answer rendered without footnote tags")
    tag = sorted(with_ranges)[0]
    return tag, int(tag.split("fn_d", 1)[1])


def _click_text_tag(app: tk.Tk, text_widget: tk.Text, tag_name: str) -> None:
    ranges = text_widget.tag_ranges(tag_name)
    if not ranges:
        raise HarnessFailure(f"tag {tag_name} has no ranges")
    index = str(ranges[0])
    text_widget.see(index)
    _pump(app, 0.10)
    bbox = text_widget.bbox(index)
    if not bbox:
        raise HarnessFailure(f"tag {tag_name} is not visible/clickable")
    x, y, width, height = bbox
    text_widget.event_generate("<Button-1>", x=x + max(1, width // 2), y=y + max(1, height // 2))
    text_widget.event_generate("<ButtonRelease-1>", x=x + max(1, width // 2), y=y + max(1, height // 2))
    _pump(app, 0.20)


def _check_semantic_query(app: tk.Tk) -> dict[str, Any]:
    qp = app.query_panel
    response = _submit_query(app, "What is CDRL A002?")
    answer_text = qp.answer_text.get("1.0", "end-1c").strip()
    if not answer_text:
        raise HarnessFailure("semantic answer area stayed empty")

    tag_name, display_num = _first_footnote_tag(qp)
    binding = qp.answer_text.tk.call(qp.answer_text._w, "tag", "bind", tag_name, "<Button-1>")
    if not binding:
        raise HarnessFailure(f"footnote tag {tag_name} has no click binding")

    trigger_mode = "event_generate"
    _click_text_tag(app, qp.answer_text, tag_name)

    if not qp._source_cards_expanded:
        trigger_mode = "direct_callback"
        qp._scroll_to_source_card(display_num)
        _pump(app, 0.20)

    if not qp._source_cards_expanded:
        raise HarnessFailure("footnote click did not expand source cards")

    card = _collect_card(qp._source_cards_container, display_num)
    border = str(card.cget("highlightbackground"))
    thickness = int(float(card.cget("highlightthickness")))
    if thickness < 2:
        raise HarnessFailure(
            f"footnote click did not highlight source card [{display_num}] (border={border}, thickness={thickness})"
        )

    if not _mapped(qp._action_frame) or not _mapped(qp._feedback_frame):
        raise HarnessFailure("copy/feedback controls did not appear after semantic query")

    if not _mapped(qp._copy_answer_btn) or not _mapped(qp._copy_sources_btn):
        raise HarnessFailure("copy buttons missing after semantic query")

    if not all(_mapped(btn) for btn in qp._feedback_btns.values()):
        raise HarnessFailure("feedback buttons missing after semantic query")

    return {
        "query_path": getattr(response, "query_path", ""),
        "confidence": getattr(response, "confidence", ""),
        "footnote_tag": tag_name,
        "display_num": display_num,
        "trigger_mode": trigger_mode,
        "sources_count": len(getattr(response, "sources", []) or []),
        "cards_count": len(qp._source_cards_container.winfo_children()),
    }


def _check_aggregation_query(app: tk.Tk) -> dict[str, Any]:
    qp = app.query_panel
    response = _submit_query(app, "top 5 failing parts in NEXION in 2024")
    answer_text = qp.answer_text.get("1.0", "end-1c")
    if getattr(response, "query_path", "") != "AGGREGATION_GREEN":
        raise HarnessFailure(f"aggregation query path was {getattr(response, 'query_path', '')!r}, expected AGGREGATION_GREEN")
    if getattr(response, "confidence", "") != "GREEN":
        raise HarnessFailure(f"aggregation confidence was {getattr(response, 'confidence', '')!r}, expected GREEN")
    if not qp.answer_text.tag_ranges("tier_green"):
        raise HarnessFailure("aggregation answer missing GREEN tier formatting")
    if not qp.answer_text.tag_ranges("table_header") and "| Rank" not in answer_text:
        raise HarnessFailure("aggregation answer missing table formatting")

    return {
        "query_path": getattr(response, "query_path", ""),
        "confidence": getattr(response, "confidence", ""),
        "latency_ms": getattr(response, "latency_ms", 0),
    }


def _check_smash_safety(app: tk.Tk, callback_errors: list[dict[str, str]]) -> dict[str, Any]:
    qp = app.query_panel
    baseline_callbacks = len(callback_errors)

    for _ in range(8):
        qp._sources_toggle_btn.invoke()
        _pump(app, 0.05)
    source_state = qp._source_cards_expanded

    qp.question_entry.delete(0, tk.END)
    qp.question_entry.insert(0, "What is CDRL A009?")
    qp.ask_btn.invoke()
    _wait_until(
        app,
        lambda: getattr(qp._model, "is_querying", False) or str(qp.stop_btn.cget("state")) == tk.NORMAL,
        15.0,
        "stop-smash query start",
    )
    for _ in range(8):
        qp.stop_btn.invoke()
        _pump(app, 0.02)
    _pump(app, 1.0)

    if len(callback_errors) != baseline_callbacks:
        raise HarnessFailure("Tk callback exceptions were raised during source/stop smash")

    return {
        "source_cards_expanded_after_even_toggles": source_state,
        "stop_state": str(qp.stop_btn.cget("state")),
        "status_label": qp._status_label.cget("text"),
    }


def run_harness(mode: str, output_dir: Path, visible: bool) -> HarnessReport:
    if mode != "real":
        raise HarnessFailure("query_panel_live_harness supports only --mode real")

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "query_panel_live_harness.log"
    json_path = output_dir / "query_panel_live_harness_report.json"
    harness_log = HarnessLogger(log_path)

    logger = logging.getLogger("query_panel_live_harness")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(file_handler)

    report = HarnessReport(started_utc=_utc_now(), artifacts={"json_report": str(json_path), "text_log": str(log_path)})
    thread_errors, original_thread_hook = _install_thread_error_trap()
    app = None
    try:
        harness_log.log("BOOT launching real HybridRAGApp surface")
        app, _config, backend_thread = _create_real_app(logger, visible=visible)
        callback_errors = _install_tk_error_trap(app)
        report.callback_errors = callback_errors
        report.thread_errors = thread_errors

        report.boot_ready_seconds = _wait_for_ready(app, harness_log)
        _run_check(report, harness_log, "default_view", lambda: _check_default_view(app))
        _run_check(report, harness_log, "admin_toggle", lambda: _check_admin_toggle(app))
        _run_check(report, harness_log, "semantic_query", lambda: _check_semantic_query(app))
        _run_check(report, harness_log, "aggregation_query", lambda: _check_aggregation_query(app))
        _run_check(report, harness_log, "smash_safety", lambda: _check_smash_safety(app, callback_errors))

        report.callback_errors = callback_errors
        report.thread_errors = thread_errors
        if callback_errors:
            raise HarnessFailure(f"Tk callback exceptions captured: {len(callback_errors)}")
        if thread_errors:
            raise HarnessFailure(f"background thread exceptions captured: {len(thread_errors)}")

        report.verdict = "PASS"
        return report
    finally:
        report.finished_utc = _utc_now()
        try:
            file_handler.flush()
            logger.removeHandler(file_handler)
            file_handler.close()
        except Exception:
            pass
        if app is not None:
            try:
                if getattr(app, "status_bar", None) is not None:
                    app.status_bar.stop()
            except Exception:
                pass
            try:
                app.destroy()
            except Exception:
                pass
        _restore_thread_error_trap(original_thread_hook)
        harness_log.write()
        json_path.write_text(json.dumps(asdict(report), indent=2, default=str), encoding="utf-8")


def _stdout_summary(report: HarnessReport) -> str:
    passed = sum(1 for check in report.checks if check.passed)
    failed = sum(1 for check in report.checks if not check.passed)
    return (
        "QUERY_PANEL_LIVE_HARNESS {verdict} checks_passed={passed} checks_failed={failed} "
        "boot_ready_seconds={ready} callback_errors={callback_errors} thread_errors={thread_errors}"
    ).format(
        verdict=report.verdict,
        passed=passed,
        failed=failed,
        ready="n/a" if report.boot_ready_seconds is None else f"{report.boot_ready_seconds:.2f}",
        callback_errors=len(report.callback_errors),
        thread_errors=len(report.thread_errors),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live harness for the real HybridRAG main query panel")
    parser.add_argument("--mode", default="real", choices=["real"], help="Only real mode is supported")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Custom artifact directory (default: output/query_panel_live_harness_<timestamp>)",
    )
    parser.add_argument(
        "--hidden",
        action="store_true",
        help="Create the real app hidden. Visible mode is the default because footnote click checks need a mapped text surface.",
    )
    args = parser.parse_args(argv)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = PROJECT_ROOT / "output" / f"query_panel_live_harness_{_slug_now()}"

    try:
        report = run_harness(mode=args.mode, output_dir=output_dir, visible=not args.hidden)
    except Exception as exc:
        json_path = output_dir / "query_panel_live_harness_report.json"
        if json_path.exists():
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            report = HarnessReport(
                tool=raw.get("tool", "tools/qa/query_panel_live_harness.py"),
                mode=raw.get("mode", "real"),
                started_utc=raw.get("started_utc", ""),
                finished_utc=raw.get("finished_utc", ""),
                boot_ready_seconds=raw.get("boot_ready_seconds"),
                verdict=raw.get("verdict", "FAIL"),
                checks=[CheckResult(**item) for item in raw.get("checks", [])],
                callback_errors=raw.get("callback_errors", []),
                thread_errors=raw.get("thread_errors", []),
                artifacts=raw.get(
                    "artifacts",
                    {
                        "json_report": str(json_path),
                        "text_log": str(output_dir / "query_panel_live_harness.log"),
                    },
                ),
            )
        else:
            report = HarnessReport(
                started_utc=_utc_now(),
                finished_utc=_utc_now(),
                verdict="FAIL",
                artifacts={
                    "json_report": str(json_path),
                    "text_log": str(output_dir / "query_panel_live_harness.log"),
                },
                checks=[
                    CheckResult(
                        check_id="fatal",
                        passed=False,
                        detail=str(exc),
                        duration_ms=0.0,
                        data={"traceback": traceback.format_exc()},
                    )
                ],
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(asdict(report), indent=2, default=str),
                encoding="utf-8",
            )
            (output_dir / "query_panel_live_harness.log").write_text(
                f"[{time.strftime('%H:%M:%S')}] FATAL {exc}\n{traceback.format_exc()}",
                encoding="utf-8",
            )
        print(_stdout_summary(report), flush=True)
        print(f"ARTIFACT json={report.artifacts['json_report']} log={report.artifacts['text_log']}", flush=True)
        return 2

    print(_stdout_summary(report), flush=True)
    print(
        "ARTIFACT json={} log={}".format(
            report.artifacts["json_report"], report.artifacts["text_log"]
        ),
        flush=True,
    )
    return 0 if report.verdict == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
