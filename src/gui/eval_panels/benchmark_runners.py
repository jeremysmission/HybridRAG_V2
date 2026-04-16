"""Background runners for the benchmark GUI panels.

These runners mirror the eval GUI's thread contract:
  - one worker thread per run
  - structured events only
  - exactly one terminal ``done`` event

They intentionally import the benchmark scripts directly so the GUI can
stream progress without depending on a subprocess shell.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

V2_ROOT = Path(__file__).resolve().parents[3]
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))


EventCallback = Callable[[str, dict], None]


class _StopRequested(Exception):
    """Raised inside a callback to cooperatively break out of a library loop."""


class _ThreadRunnerBase:
    """Structured helper object used by the benchmark runners workflow."""
    def __init__(self, on_event: EventCallback):
        self._on_event = on_event
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        if not self.is_alive:
            return
        self._stop_event.set()
        self._emit("log", {"msg": "Stop requested -- finishing current item.", "level": "WARN"})

    def _emit(self, kind: str, payload: dict) -> None:
        try:
            self._on_event(kind, payload)
        except Exception:
            pass


class AggregationBenchmarkRunner(_ThreadRunnerBase):
    """Run the aggregation benchmark in a background thread."""

    def start(
        self,
        *,
        manifest_path: Path,
        answers_path: Path | None,
        output_path: Path,
        min_pass_rate: float,
    ) -> None:
        if self.is_alive:
            self._emit("log", {"msg": "Aggregation runner already active.", "level": "WARN"})
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            kwargs={
                "manifest_path": Path(manifest_path),
                "answers_path": Path(answers_path) if answers_path else None,
                "output_path": Path(output_path),
                "min_pass_rate": float(min_pass_rate),
            },
            name="AggregationBenchmarkRunner",
            daemon=True,
        )
        self._thread.start()

    def _run(
        self,
        *,
        manifest_path: Path,
        answers_path: Path | None,
        output_path: Path,
        min_pass_rate: float,
    ) -> None:
        t_start = time.time()
        status = "FAILED"
        try:
            from scripts import run_aggregation_benchmark_2026_04_15 as agg

            self._emit("phase", {"phase": "VALIDATE"})
            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found: {manifest_path}")
            if answers_path and not answers_path.exists():
                raise FileNotFoundError(f"Answers file not found: {answers_path}")

            manifest = agg.load_manifest(manifest_path)
            answers = agg.load_answers(answers_path) if answers_path else None
            answer_map = answers or {}
            self_check = answers is None
            items = manifest["items"]
            total = len(items)

            self._emit(
                "log",
                {
                    "msg": f"Loaded {total} aggregation items from {manifest_path.name}",
                    "level": "INFO",
                },
            )
            self._emit("phase", {"phase": "RUN"})

            results = []
            for idx, raw in enumerate(items, 1):
                if self._stop_event.is_set():
                    status = "STOPPED"
                    self._emit("log", {"msg": "Stopped by operator.", "level": "WARN"})
                    break
                item = agg.BenchmarkItem(**raw)
                actual_answer = (
                    item.expected_answer if self_check and item.id not in answer_map else answer_map.get(item.id)
                )
                passed, detail = agg.score_answer(item.expected_answer, actual_answer)
                result = agg.ItemResult(
                    id=item.id,
                    family=item.family,
                    question=item.question,
                    expected_answer=item.expected_answer,
                    actual_answer=actual_answer,
                    passed=passed,
                    detail=detail,
                )
                results.append(result)
                level = "OK" if passed else "ERROR"
                rendered_answer = agg._normalize_text(actual_answer) or "<missing>"
                self._emit(
                    "log",
                    {
                        "msg": (
                            f"[{'PASS' if passed else 'FAIL'}] {item.id} "
                            f"expected={item.expected_answer} actual={rendered_answer}"
                        ),
                        "level": level,
                    },
                )
                self._emit("progress", {"current": idx, "total": total})

            pass_count = sum(1 for result in results if result.passed)
            fail_count = total - pass_count
            pass_rate = (pass_count / total) if total else 0.0
            gate_pass = pass_rate >= min_pass_rate and fail_count == 0
            summary = agg.BenchmarkSummary(
                benchmark_id=str(manifest.get("benchmark_id", "aggregation_benchmark")),
                manifest_path=str(manifest_path),
                mode="self-check" if self_check else "score",
                total_items=total,
                pass_count=pass_count,
                fail_count=fail_count,
                pass_rate=pass_rate,
                gate_pass=gate_pass,
                results=[asdict(result) for result in results],
            )

            self._emit("phase", {"phase": "WRITE"})
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(asdict(summary), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            status = "PASS" if gate_pass else "FAIL"
            self._emit(
                "log",
                {
                    "msg": (
                        f"Aggregation benchmark complete: {summary.pass_count}/{summary.total_items} "
                        f"passed ({summary.pass_rate:.3f})"
                    ),
                    "level": "OK" if gate_pass else "WARN",
                },
            )
            done_payload = {
                "status": status,
                "error": None,
                "elapsed_s": round(time.time() - t_start, 1),
                "summary": asdict(summary),
                "artifact_paths": {"output_json": str(output_path)},
                "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self._emit("log", {"msg": traceback.format_exc(), "level": "ERROR"})
            done_payload = {
                "status": status,
                "error": error,
                "elapsed_s": round(time.time() - t_start, 1),
                "summary": None,
                "artifact_paths": {"output_json": str(output_path)},
                "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
        self._emit("done", done_payload)


class CountBenchmarkRunner(_ThreadRunnerBase):
    """Run the count benchmark in a background thread."""

    def start(
        self,
        *,
        targets_path: Path,
        lance_db: Path,
        entity_db: Path,
        output_dir: Path,
        modes: tuple[str, ...],
        include_deferred: bool,
        predictions_json: Path | None,
    ) -> None:
        if self.is_alive:
            self._emit("log", {"msg": "Count runner already active.", "level": "WARN"})
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            kwargs={
                "targets_path": Path(targets_path),
                "lance_db": Path(lance_db),
                "entity_db": Path(entity_db),
                "output_dir": Path(output_dir),
                "modes": tuple(modes),
                "include_deferred": bool(include_deferred),
                "predictions_json": Path(predictions_json) if predictions_json else None,
            },
            name="CountBenchmarkRunner",
            daemon=True,
        )
        self._thread.start()

    def _run(
        self,
        *,
        targets_path: Path,
        lance_db: Path,
        entity_db: Path,
        output_dir: Path,
        modes: tuple[str, ...],
        include_deferred: bool,
        predictions_json: Path | None,
    ) -> None:
        t_start = time.time()
        status = "FAILED"
        store = None
        entity_conn = None
        row_conn = None
        json_path = None
        md_path = None
        try:
            from scripts import count_benchmark as cb
            from src.store.lance_store import LanceStore

            self._emit("phase", {"phase": "VALIDATE"})
            if not targets_path.exists():
                raise FileNotFoundError(f"Target set not found: {targets_path}")
            if not lance_db.exists():
                raise FileNotFoundError(f"LanceDB path not found: {lance_db}")
            if not entity_db.exists():
                raise FileNotFoundError(f"Entity DB not found: {entity_db}")
            if predictions_json and not predictions_json.exists():
                raise FileNotFoundError(f"Predictions JSON not found: {predictions_json}")
            if not modes:
                raise ValueError("At least one count mode must be selected.")

            lane_name, lane_date, loaded_targets = cb.load_target_set(targets_path)
            targets = cb.select_targets(loaded_targets, include_deferred=include_deferred)
            if not targets:
                raise ValueError("No targets selected after audited/deferred filtering.")

            self._emit(
                "log",
                {
                    "msg": f"Loaded {len(targets)} count targets ({lane_name})",
                    "level": "INFO",
                },
            )

            predictions_by_target = cb.load_predictions(predictions_json) if predictions_json else None

            self._emit("phase", {"phase": "OPEN_STORES"})
            output_dir.mkdir(parents=True, exist_ok=True)
            store = LanceStore(str(lance_db))
            entity_conn = sqlite3.connect(f"file:{entity_db.as_posix()}?mode=ro", uri=True)
            entity_conn.row_factory = sqlite3.Row
            row_conn = sqlite3.connect(f"file:{entity_db.as_posix()}?mode=ro", uri=True)
            row_conn.row_factory = sqlite3.Row

            self._emit("phase", {"phase": "RUN"})
            results = []
            total = len(targets)
            for idx, target in enumerate(targets, 1):
                if self._stop_event.is_set():
                    status = "STOPPED"
                    self._emit("log", {"msg": "Stopped by operator.", "level": "WARN"})
                    break
                self._emit(
                    "log",
                    {
                        "msg": f"[{idx}/{total}] {target.target} [{target.surface}]",
                        "level": "INFO",
                    },
                )
                result = cb.count_target(
                    target,
                    store,
                    entity_conn,
                    row_conn,
                    modes=modes,
                    predictions_by_target=predictions_by_target,
                )
                results.append(result)
                self._emit(
                    "log",
                    {
                        "msg": (
                            f"    counts raw={result.counts['raw_mentions']} "
                            f"docs={result.counts['unique_documents']} "
                            f"chunks={result.counts['unique_chunks']} "
                            f"rows={result.counts['unique_rows']}"
                        ),
                        "level": "OK" if result.expected_exact_match is not False else "WARN",
                    },
                )
                self._emit("progress", {"current": idx, "total": total})

            summary = cb.summarize_results(results, modes)
            payload = {
                "lane_name": lane_name,
                "lane_date": lane_date,
                "targets_path": str(targets_path),
                "lance_db": str(lance_db),
                "entity_db": str(entity_db),
                "selected_target_count": len(targets),
                "modes": list(modes),
                "predictions_json": str(predictions_json) if predictions_json else None,
                "summary": summary,
                "results": [asdict(result) for result in results],
            }

            self._emit("phase", {"phase": "WRITE"})
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            json_path = output_dir / f"count_benchmark_{timestamp}.json"
            md_path = output_dir / f"count_benchmark_{timestamp}.md"
            json_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            md_path.write_text(
                cb.build_markdown(
                    results,
                    lane_name,
                    lane_date,
                    targets_path,
                    include_deferred,
                    modes,
                    predictions_json,
                ),
                encoding="utf-8",
                newline="\n",
            )
            status = "PASS"
            self._emit(
                "log",
                {
                    "msg": (
                        f"Count benchmark complete: {summary['selected_targets']} targets, "
                        f"{summary['expected_exact']}/{summary['expected_total']} frozen exact"
                    ),
                    "level": "OK",
                },
            )
            done_payload = {
                "status": status,
                "error": None,
                "elapsed_s": round(time.time() - t_start, 1),
                "lane_name": lane_name,
                "lane_date": lane_date,
                "summary": summary,
                "artifact_paths": {
                    "output_json": str(json_path),
                    "output_md": str(md_path),
                },
                "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self._emit("log", {"msg": traceback.format_exc(), "level": "ERROR"})
            done_payload = {
                "status": status,
                "error": error,
                "elapsed_s": round(time.time() - t_start, 1),
                "lane_name": "",
                "lane_date": "",
                "summary": None,
                "artifact_paths": {
                    "output_json": str(json_path) if json_path else "",
                    "output_md": str(md_path) if md_path else "",
                },
                "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            try:
                if entity_conn is not None:
                    entity_conn.close()
            except Exception:
                pass
            try:
                if row_conn is not None:
                    row_conn.close()
            except Exception:
                pass
            try:
                if store is not None:
                    store.close()
            except Exception:
                pass
        self._emit("done", done_payload)


class RagasEvalRunner(_ThreadRunnerBase):
    """Run the RAGAS readiness/eval flow in a background thread."""

    def start(
        self,
        *,
        queries_path: Path,
        output_path: Path,
        limit: int | None,
        analysis_only: bool,
        top_k: int,
    ) -> None:
        if self.is_alive:
            self._emit("log", {"msg": "RAGAS runner already active.", "level": "WARN"})
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            kwargs={
                "queries_path": Path(queries_path),
                "output_path": Path(output_path),
                "limit": int(limit) if limit is not None else None,
                "analysis_only": bool(analysis_only),
                "top_k": int(top_k),
            },
            name="RagasEvalRunner",
            daemon=True,
        )
        self._thread.start()

    def _run(
        self,
        *,
        queries_path: Path,
        output_path: Path,
        limit: int | None,
        analysis_only: bool,
        top_k: int,
    ) -> None:
        t_start = time.time()
        status = "FAILED"
        try:
            from scripts import run_ragas_eval as ragas_eval

            self._emit("phase", {"phase": "VALIDATE"})
            if not queries_path.exists():
                raise FileNotFoundError(f"Query file not found: {queries_path}")
            if limit is not None and limit <= 0:
                raise ValueError("Limit must be a positive integer when provided.")
            if top_k <= 0:
                raise ValueError("Top-K must be positive.")

            queries, metadata_blocks = ragas_eval.load_queries(queries_path)
            readiness = ragas_eval.analyze_readiness(queries)
            probe = ragas_eval.probe_dependencies()
            readiness_summary = ragas_eval.build_readiness_summary(
                queries,
                readiness,
                metadata_blocks,
                queries_path,
            )
            dependency_summary = ragas_eval.build_dependency_summary(probe)

            eligible = readiness_summary["eligible_for_retrieval_metrics"]
            total_queries = readiness_summary["total_queries"]
            phase2c_ready = readiness_summary["fully_phase2c_enriched"]

            self._emit("log", {"msg": f"Loaded {total_queries} queries from {queries_path.name}", "level": "INFO"})
            self._emit(
                "log",
                {
                    "msg": (
                        f"Retrieval-ready: {eligible}/{total_queries} | "
                        f"Phase2C-ready: {phase2c_ready}/{total_queries}"
                    ),
                    "level": "INFO",
                },
            )
            if dependency_summary["blockers"]:
                self._emit(
                    "log",
                    {
                        "msg": "Dependency blockers: " + ", ".join(dependency_summary["blockers"]),
                        "level": "WARN",
                    },
                )
            else:
                self._emit("log", {"msg": "Dependency probe clean.", "level": "OK"})

            metric_summaries = []
            skip_reasons: dict[str, int] = {}
            pipeline_info: dict[str, object] = {}

            if analysis_only:
                status = "PASS"
                self._emit("phase", {"phase": "ANALYSIS_ONLY"})
                self._emit("progress", {"current": total_queries, "total": total_queries or 1})
                self._emit("log", {"msg": "Analysis-only mode selected; execution skipped.", "level": "INFO"})
            elif not probe.ragas_installed:
                status = "BLOCKED"
                self._emit("phase", {"phase": "BLOCKED"})
                self._emit(
                    "log",
                    {"msg": "RAGAS execution blocked: ragas is not installed in the project venv.", "level": "WARN"},
                )
            else:
                self._emit("phase", {"phase": "RUN"})

                def _progress(current: int, total: int, _query) -> None:
                    if self._stop_event.is_set():
                        raise _StopRequested()
                    self._emit("progress", {"current": current, "total": total or 1})

                def _log(msg: str, level: str = "INFO") -> None:
                    self._emit("log", {"msg": msg, "level": level})

                try:
                    summaries, raw_skip_reasons, pipeline_info = ragas_eval.execute_metrics(
                        queries=queries,
                        readiness=readiness,
                        probe=probe,
                        top_k=top_k,
                        limit=limit,
                        progress_cb=_progress,
                        log_cb=_log,
                    )
                except _StopRequested:
                    status = "STOPPED"
                    self._emit("log", {"msg": "Stopped by operator.", "level": "WARN"})
                    summaries = []
                    raw_skip_reasons = {}

                if status != "STOPPED":
                    metric_summaries = ragas_eval.serialize_metric_summaries(summaries)
                    skip_reasons = dict(raw_skip_reasons)
                    status = "PASS"
                for summary in metric_summaries:
                    self._emit(
                        "log",
                        {
                            "msg": (
                                f"metric {summary['name']}: mean={summary['mean']} "
                                f"median={summary['median']} count={summary['count']} errors={summary['errors']}"
                            ),
                            "level": "OK" if summary["errors"] == 0 else "WARN",
                        },
                    )

            summary = {
                "surface": "RAGAS",
                "queries_path": str(queries_path),
                "queries_pack_name": queries_path.name,
                "analysis_only": analysis_only,
                "limit": limit,
                "top_k": top_k,
                "readiness": readiness_summary,
                "dependencies": dependency_summary,
                "metric_summaries": metric_summaries,
                "skip_reasons": skip_reasons,
                "pipeline_info": pipeline_info,
                "proof_text": (
                    f"eligible={eligible}/{total_queries}; "
                    f"phase2c_ready={phase2c_ready}/{total_queries}; "
                    f"ragas_installed={'yes' if dependency_summary['ragas_installed'] else 'no'}"
                ),
            }

            self._emit("phase", {"phase": "WRITE"})
            output_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "summary": summary,
                "artifact_paths": {"output_json": str(output_path)},
            }
            output_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            done_payload = {
                "status": status,
                "error": None,
                "elapsed_s": round(time.time() - t_start, 1),
                "surface": "RAGAS",
                "run_id": payload["run_id"],
                "timestamp_utc": payload["timestamp_utc"],
                "queries_path": str(queries_path),
                "queries_pack_name": queries_path.name,
                "analysis_only": analysis_only,
                "limit": limit,
                "top_k": top_k,
                "summary": summary,
                "artifact_paths": {"output_json": str(output_path)},
                "proof_text": summary["proof_text"],
            }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self._emit("log", {"msg": traceback.format_exc(), "level": "ERROR"})
            done_payload = {
                "status": status,
                "error": error,
                "elapsed_s": round(time.time() - t_start, 1),
                "surface": "RAGAS",
                "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "queries_path": str(queries_path),
                "queries_pack_name": queries_path.name,
                "analysis_only": analysis_only,
                "limit": limit,
                "top_k": top_k,
                "summary": None,
                "artifact_paths": {"output_json": str(output_path)},
                "proof_text": "",
            }
        self._emit("done", done_payload)
