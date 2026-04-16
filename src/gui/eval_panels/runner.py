"""EvalRunner -- background worker for the production eval GUI.

Wraps `scripts/run_production_eval.py` internals so we can stream
progress into the GUI without forking a subprocess. The runner owns one
worker thread, a cooperative stop event, and a structured-message
callback contract that the launch panel consumes via safe_after.

Threading model mirrors `scripts/import_extract_gui.py`:
    - start() spawns a daemon thread
    - _run() on the worker does all heavy lifting
    - stop() sets an Event that the worker polls between queries
    - all UI updates are routed through on_event(kind, payload)
      which the caller guarantees to be thread-safe (safe_after)

Terminal contract: exactly one "done" event is emitted (with status
"PASS" / "STOPPED" / "FAILED") before the thread exits.
"""

from __future__ import annotations

import json
import os
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


def _pct(numerator: int, denominator: int) -> float:
    """Support the runner workflow by handling the pct step."""
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 1)


def _fmt_pct(value: float) -> str:
    """Turn internal values into human-readable text for the operator."""
    text = f"{value:.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return f"{text}%"


def _bucket_quality_rows(scorecard: dict, dimension: str) -> list[dict]:
    """Normalize per-bucket scorecards into ranked rows for UI/history summaries.

    Score uses PASS + 0.5 * PARTIAL so "mostly good with some partials" sorts
    above buckets with the same raw PASS rate but more misses.
    """
    rows: list[dict] = []
    for name, stats in (scorecard or {}).items():
        try:
            total = int((stats or {}).get("total") or 0)
            passed = int((stats or {}).get("PASS") or 0)
            partial = int((stats or {}).get("PARTIAL") or 0)
            miss = int((stats or {}).get("MISS") or 0)
            routing_correct = int((stats or {}).get("routing_correct") or 0)
        except Exception:
            continue
        if total <= 0:
            continue
        score_pct = round((((passed + (0.5 * partial)) / total) * 100.0), 1)
        pass_rate_pct = _pct(passed, total)
        rows.append(
            {
                "dimension": dimension,
                "name": str(name),
                "total": total,
                "pass_count": passed,
                "partial_count": partial,
                "miss_count": miss,
                "routing_correct": routing_correct,
                "score_pct": score_pct,
                "pass_rate_pct": pass_rate_pct,
                "routing_pct": _pct(routing_correct, total),
            }
        )
    return rows


def _format_bucket_lines(rows: list[dict], include_dimension: bool = False) -> list[str]:
    """Turn internal values into human-readable text for the operator."""
    lines: list[str] = []
    for row in rows:
        prefix = f"{row['dimension']}: " if include_dimension else ""
        suffix = f", n={row['total']}" if include_dimension else ""
        lines.append(f"{prefix}{row['name']} ({_fmt_pct(row['score_pct'])}{suffix})")
    return lines


def _rank_area_rows(rows: list[dict], top_n: int = 3) -> tuple[list[dict], list[dict]]:
    """Support the runner workflow by handling the rank area rows step."""
    if not rows:
        return [], []

    strongest = sorted(
        rows,
        key=lambda row: (-row["score_pct"], -row["total"], -row["pass_rate_pct"], row["name"]),
    )[:top_n]
    weakest = sorted(
        rows,
        key=lambda row: (row["score_pct"], -row["total"], row["pass_rate_pct"], row["name"]),
    )[:top_n]
    return strongest, weakest


class EvalRunner:
    """Runs the production eval in a worker thread, streams live events.

    Parameters
    ----------
    on_event:
        Callable that receives (event_kind, payload) from the worker
        thread. The caller MUST route this through safe_after or an
        equivalent main-thread-safe mechanism.

    Event kinds emitted
    -------------------
    log        -- payload: {"msg": str, "level": "INFO"|"WARN"|"ERROR"}
    phase      -- payload: {"phase": str}
    progress   -- payload: {"current": int, "total": int}
    query      -- payload: dict (one query's result summary)
    scorecard  -- payload: dict (final scorecard stats)
    done       -- payload: {"status": "PASS"|"STOPPED"|"FAILED",
                             "results_json": str, "report_md": str,
                             "error": str | None}
    """

    def __init__(self, on_event: EventCallback):
        self._on_event = on_event
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(
        self,
        queries_path: Path,
        config_path: Path,
        report_md: Path,
        results_json: Path,
        gpu_index: str = "0",
        max_queries: Optional[int] = None,
    ) -> None:
        if self.is_alive:
            self._emit("log", {"msg": "Runner already running; ignoring start.", "level": "WARN"})
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(queries_path, config_path, report_md, results_json, gpu_index, max_queries),
            name="EvalRunner",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if not self.is_alive:
            return
        self._stop_event.set()
        self._emit("log", {"msg": "Stop requested -- waiting for current query to finish.", "level": "WARN"})

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Worker body
    # ------------------------------------------------------------------
    def _run(
        self,
        queries_path: Path,
        config_path: Path,
        report_md: Path,
        results_json: Path,
        gpu_index: str,
        max_queries: Optional[int],
    ) -> None:
        t_start = time.time()
        status = "FAILED"
        error: Optional[str] = None
        try:
            self._emit("phase", {"phase": "BOOT"})
            self._emit("log", {"msg": f"GPU requested: CUDA_VISIBLE_DEVICES={gpu_index}", "level": "INFO"})

            os.environ["CUDA_VISIBLE_DEVICES"] = gpu_index

            import torch  # noqa: E402

            os.environ["CUDA_VISIBLE_DEVICES"] = "0"

            if not torch.cuda.is_available():
                raise RuntimeError("CUDA not available -- eval requires GPU.")
            gpu_name = torch.cuda.get_device_name(0)
            self._emit("log", {"msg": f"GPU bound: CUDA_VISIBLE_DEVICES={gpu_index} -> cuda:0 ({gpu_name})", "level": "INFO"})

            from scripts import run_production_eval as rpe  # type: ignore
            from src.config.schema import load_config
            from src.store.lance_store import LanceStore
            from src.query.embedder import Embedder
            from src.query.vector_retriever import VectorRetriever
            from src.query.context_builder import ContextBuilder
            from src.query.query_router import QueryRouter
            from src.query.pipeline import QueryPipeline
            from src.llm.client import LLMClient

            self._emit("phase", {"phase": "CONFIG"})
            self._emit("log", {"msg": f"Queries: {queries_path}", "level": "INFO"})
            self._emit("log", {"msg": f"Config:  {config_path}", "level": "INFO"})

            if not queries_path.exists():
                raise FileNotFoundError(f"Queries pack not found: {queries_path}")
            if not config_path.exists():
                raise FileNotFoundError(f"Config not found: {config_path}")

            with open(queries_path, encoding="utf-8") as f:
                raw = json.load(f)
            queries = [q for q in raw if rpe._get_query_id(q) and rpe._get_query_text(q)]
            if max_queries is not None:
                queries = queries[: int(max_queries)]
            total = len(queries)
            self._emit("log", {"msg": f"Loaded {total} queries.", "level": "INFO"})
            if total == 0:
                raise RuntimeError("No usable queries in pack.")

            self._emit("phase", {"phase": "LOAD_STORE"})
            config = load_config(str(config_path))
            lance_path = str(Path(config.paths.lance_db))
            store = LanceStore(lance_path)
            store_count = store.count()
            self._emit("log", {"msg": f"Store: {store_count:,} chunks at {lance_path}", "level": "INFO"})

            self._emit("phase", {"phase": "LOAD_EMBEDDER"})
            embedder = Embedder(model_name="nomic-ai/nomic-embed-text-v1.5", dim=768, device="cuda")

            retriever = VectorRetriever(
                store,
                embedder,
                top_k=rpe.TOP_K,
                candidate_pool=config.retrieval.candidate_pool,
            )
            ctx_builder = ContextBuilder(
                top_k=rpe.TOP_K,
                reranker_enabled=config.retrieval.reranker_enabled,
            )
            llm_client = LLMClient()
            router = QueryRouter(llm_client)
            llm_requested_provider = (getattr(config.llm, "provider", "") or "").strip()
            router_mode = "llm" if llm_client.available else "rule-based fallback"
            provider = (getattr(llm_client, "provider", "") or llm_requested_provider or "").strip()
            if provider == "auto":
                provider = ""
            if llm_client.available:
                model = (
                    (getattr(llm_client, "deployment", "") or "").strip()
                    if provider == "azure"
                    else (getattr(llm_client, "model", "") or "").strip()
                )
            else:
                model = ""
            if not llm_client.available:
                self._emit("log", {"msg": "Router: rule-based fallback (LLM unavailable).", "level": "INFO"})
            else:
                model_label = f" / {model}" if model else ""
                self._emit("log", {"msg": f"Router: LLM available ({provider}{model_label}).", "level": "INFO"})

            entity_retriever = None
            entity_db_path = V2_ROOT / config.paths.entity_db
            if entity_db_path.exists():
                try:
                    from src.store.entity_store import EntityStore
                    from src.store.relationship_store import RelationshipStore
                    from src.query.entity_retriever import EntityRetriever
                    entity_retriever = EntityRetriever(
                        EntityStore(str(entity_db_path)),
                        RelationshipStore(str(entity_db_path)),
                    )
                    self._emit("log", {"msg": f"Entity store: {entity_db_path}", "level": "INFO"})
                except Exception as e:
                    self._emit("log", {"msg": f"Entity store init failed (non-fatal): {e}", "level": "WARN"})

            pipeline = QueryPipeline(
                router=router,
                vector_retriever=retriever,
                entity_retriever=entity_retriever,
                context_builder=ctx_builder,
                generator=None,
                crag_verifier=None,
            )

            self._emit("phase", {"phase": "RUN"})
            results = []
            for i, qdef in enumerate(queries, 1):
                if self._stop_event.is_set():
                    self._emit("log", {"msg": f"Stop honored at query {i}/{total}.", "level": "WARN"})
                    status = "STOPPED"
                    break
                qid = rpe._get_query_id(qdef) or f"?{i}"
                persona = qdef.get("persona", "?")
                r = rpe.run_query(qdef, pipeline)
                results.append(r)
                self._emit("progress", {"current": i, "total": total})
                self._emit(
                    "query",
                    {
                        "index": i,
                        "query_id": qid,
                        "persona": persona,
                        "verdict": r.verdict,
                        "top_in_family": bool(r.top_in_family),
                        "any_top5_in_family": bool(r.any_top5_in_family),
                        "routed_query_type": r.routed_query_type,
                        "routing_correct": bool(r.routing_correct),
                        "embed_retrieve_ms": int(r.embed_retrieve_ms),
                        "error": r.error,
                    },
                )

            if status != "STOPPED":
                status = "PASS"

            self._emit("phase", {"phase": "AGGREGATE"})
            pass_count = sum(1 for r in results if r.verdict == "PASS")
            partial_count = sum(1 for r in results if r.verdict == "PARTIAL")
            miss_count = sum(1 for r in results if r.verdict == "MISS")
            routing_correct = sum(1 for r in results if r.routing_correct)
            pure_retrieval = [r.retrieval_ms for r in results if not r.error]
            wall_clock = [r.embed_retrieve_ms for r in results if not r.error]
            router_latencies = [r.router_ms for r in results if not r.error]
            per_persona = rpe._scorecard(results, lambda r: r.persona)
            per_query_type = rpe._scorecard(results, lambda r: r.expected_query_type)
            run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            timestamp_utc = datetime.now(timezone.utc).isoformat()
            gpu_device = f"CUDA_VISIBLE_DEVICES={gpu_index} -> cuda:0 (NVIDIA workstation GPU)"
            run = rpe.EvalRun(
                run_id=run_id,
                timestamp_utc=timestamp_utc,
                store_chunks=store_count,
                gpu_device=gpu_device,
                total_queries=len(results),
                pass_count=pass_count,
                partial_count=partial_count,
                miss_count=miss_count,
                routing_correct=routing_correct,
                p50_pure_retrieval_ms=rpe._percentile(pure_retrieval, 50),
                p95_pure_retrieval_ms=rpe._percentile(pure_retrieval, 95),
                p50_wall_clock_ms=rpe._percentile(wall_clock, 50),
                p95_wall_clock_ms=rpe._percentile(wall_clock, 95),
                p50_router_ms=rpe._percentile(router_latencies, 50),
                p95_router_ms=rpe._percentile(router_latencies, 95),
                per_persona=per_persona,
                per_query_type=per_query_type,
                results=[asdict(r) for r in results],
            )

            persona_rows = _bucket_quality_rows(per_persona, "persona")
            query_type_rows = _bucket_quality_rows(per_query_type, "query_type")
            strongest_persona_rows, weakest_persona_rows = _rank_area_rows(persona_rows)
            strongest_query_type_rows, weakest_query_type_rows = _rank_area_rows(query_type_rows)
            strongest_area_rows, weakest_area_rows = _rank_area_rows(query_type_rows + persona_rows)

            strongest_personas = _format_bucket_lines(strongest_persona_rows)
            weakest_personas = _format_bucket_lines(weakest_persona_rows)
            strongest_query_types = _format_bucket_lines(strongest_query_type_rows)
            weakest_query_types = _format_bucket_lines(weakest_query_type_rows)
            strongest_areas = _format_bucket_lines(strongest_area_rows, include_dimension=True)
            weakest_areas = _format_bucket_lines(weakest_area_rows, include_dimension=True)

            elapsed_s = round(time.time() - t_start, 1)
            artifact_paths = {
                "results_json": str(results_json),
                "report_md": str(report_md),
            }
            score_summary = {
                "status": status,
                "total_queries": len(results),
                "pass_count": pass_count,
                "partial_count": partial_count,
                "miss_count": miss_count,
                "routing_correct": routing_correct,
                "pass_rate_pct": _pct(pass_count, len(results)),
                "partial_rate_pct": _pct(partial_count, len(results)),
                "miss_rate_pct": _pct(miss_count, len(results)),
                "routing_rate_pct": _pct(routing_correct, len(results)),
            }
            latency_summary = {
                "p50_pure_retrieval_ms": run.p50_pure_retrieval_ms,
                "p95_pure_retrieval_ms": run.p95_pure_retrieval_ms,
                "p50_wall_clock_ms": run.p50_wall_clock_ms,
                "p95_wall_clock_ms": run.p95_wall_clock_ms,
                "p50_router_ms": run.p50_router_ms,
                "p95_router_ms": run.p95_router_ms,
                "elapsed_s": elapsed_s,
            }
            run_summary = {
                "overall_pass_rate_pct": score_summary["pass_rate_pct"],
                "category_min_pass_rate_pct": min(
                    [row["score_pct"] for row in query_type_rows],
                    default=0.0,
                ),
                "score_summary": score_summary,
                "latency_summary": latency_summary,
                "stage_latency_summary": run.stage_latency_summary,
                "strongest_areas": strongest_areas,
                "weakest_areas": weakest_areas,
                "strongest_personas": strongest_personas,
                "weakest_personas": weakest_personas,
                "strongest_query_types": strongest_query_types,
                "weakest_query_types": weakest_query_types,
                "strongest_area_rows": strongest_area_rows,
                "weakest_area_rows": weakest_area_rows,
                "persona_rows": persona_rows,
                "query_type_rows": query_type_rows,
            }

            rpe.RESULTS_JSON = results_json
            rpe.REPORT_MD = report_md
            rpe.REPORT_QUERY_LABEL = (
                str(queries_path.relative_to(V2_ROOT)).replace("\\", "/")
                if queries_path.is_relative_to(V2_ROOT)
                else str(queries_path)
            )
            rpe.REPORT_CONFIG_LABEL = (
                str(config_path.relative_to(V2_ROOT)).replace("\\", "/")
                if config_path.is_relative_to(V2_ROOT)
                else str(config_path)
            )
            rpe.write_json_results(run)
            rpe.write_markdown_report(run, results)

            # ---- Post-write provenance injection ------------------------------
            # Add audit fields the base EvalRun dataclass does not persist so
            # repeated runs can be told apart in results/history/compare views
            # (queries pack used, config used, store path, output paths, GPU
            # label, wall-clock elapsed, source source runner tag). Kept as a
            # narrow post-write patch so we do not widen the scope of
            # scripts/run_production_eval.py.
            try:
                provenance = {
                    "run_id": run_id,
                    "timestamp_utc": timestamp_utc,
                    "queries_path": str(queries_path),
                    "query_pack": queries_path.name,
                    "queries_pack_name": queries_path.name,
                    "config_path": str(config_path),
                    "config_name": config_path.name,
                    "store_path": lance_path,
                    "lance_path": lance_path,
                    "report_md_path": str(report_md),
                    "results_json_path": str(results_json),
                    "artifact_paths": artifact_paths,
                    "gpu_device": gpu_device,
                    "gpu_index_requested": gpu_index,
                    "max_queries_requested": max_queries,
                    "router_mode": router_mode,
                    "llm_available": bool(llm_client.available),
                    "provider": provider,
                    "model": model,
                    "run_status": status,
                    "elapsed_s": elapsed_s,
                    "runner_source": "src.gui.eval_panels.runner.EvalRunner",
                    "run_summary": run_summary,
                }
                with open(results_json, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if isinstance(existing, dict):
                    if not existing.get("timestamp_utc"):
                        existing["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
                    existing["provenance"] = provenance
                    with open(results_json, "w", encoding="utf-8") as f:
                        json.dump(existing, f, indent=2, default=str)
                    self._emit(
                        "log",
                        {
                            "msg": f"Provenance written: queries={queries_path.name} config={config_path.name}",
                            "level": "INFO",
                        },
                    )
            except Exception as provenance_exc:
                self._emit(
                    "log",
                    {
                        "msg": f"Provenance injection failed (non-fatal): {provenance_exc}",
                        "level": "WARN",
                    },
                )

            self._emit(
                "scorecard",
                {
                    "total": len(results),
                    "pass": pass_count,
                    "partial": partial_count,
                    "miss": miss_count,
                    "routing_correct": routing_correct,
                    "p50_pure_retrieval_ms": run.p50_pure_retrieval_ms,
                    "p95_pure_retrieval_ms": run.p95_pure_retrieval_ms,
                    "p50_wall_clock_ms": run.p50_wall_clock_ms,
                    "p95_wall_clock_ms": run.p95_wall_clock_ms,
                    "elapsed_s": elapsed_s,
                    "provider": provider,
                    "model": model,
                    "router_mode": router_mode,
                    "score_summary": score_summary,
                    "latency_summary": latency_summary,
                    "stage_latency_summary": run.stage_latency_summary,
                    "strongest_areas": strongest_areas,
                    "weakest_areas": weakest_areas,
                    "strongest_query_types": strongest_query_types,
                    "weakest_query_types": weakest_query_types,
                    "strongest_personas": strongest_personas,
                    "weakest_personas": weakest_personas,
                },
            )
            try:
                store.close()
            except Exception:
                pass
        except Exception as exc:
            status = "FAILED"
            error = f"{type(exc).__name__}: {exc}"
            tb = traceback.format_exc()
            self._emit("log", {"msg": tb, "level": "ERROR"})
        finally:
            self._emit(
                "done",
                {
                    "status": status,
                    "results_json": str(results_json),
                    "report_md": str(report_md),
                    "error": error,
                    "elapsed_s": round(time.time() - t_start, 1),
                    "run_id": locals().get("run_id"),
                    "timestamp_utc": locals().get("timestamp_utc"),
                    "queries_pack_name": locals().get("queries_path").name if "queries_path" in locals() else "",
                    "config_name": locals().get("config_path").name if "config_path" in locals() else "",
                    "config_path": str(locals().get("config_path")) if "config_path" in locals() else "",
                    "store_path": locals().get("lance_path", ""),
                    "provider": locals().get("provider", ""),
                    "model": locals().get("model", ""),
                    "router_mode": locals().get("router_mode", ""),
                    "score_summary": locals().get("score_summary", {}),
                    "latency_summary": locals().get("latency_summary", {}),
                    "strongest_areas": locals().get("strongest_areas", []),
                    "weakest_areas": locals().get("weakest_areas", []),
                    "artifact_paths": locals().get("artifact_paths", {}),
                },
            )

    def _emit(self, kind: str, payload: dict) -> None:
        try:
            self._on_event(kind, payload)
        except Exception:
            pass
