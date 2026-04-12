"""
RAGAS execution runner for the production 400-query corpus.

This script is intentionally read-only:
  - reads the live query JSON
  - reports which queries are ready for retrieval-side RAGAS metrics
  - optionally runs supported RAGAS metrics when the dependency is installed

Current scope is deliberately narrow:
  - retrieval-side, non-LLM metrics only
  - no mutation of the source query file
  - safe handling of partially enriched Phase 2C state
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.util
import json
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERIES = (
    REPO_ROOT / "tests" / "golden_eval" / "production_queries_400_2026-04-12.json"
)
DEFAULT_TOP_K = 5


@dataclass
class QueryDefinition:
    row_index: int
    query_id: str
    has_query_id: bool
    user_input: str
    has_user_input: bool
    persona: str
    expected_query_type: str
    expected_document_family: str
    reference: str | None
    reference_contexts: list[str]
    expected_source_patterns: list[str]
    has_ground_truth: bool


@dataclass
class ReadinessRecord:
    query_id: str
    eligible_for_retrieval_metrics: bool
    fully_phase2c_enriched: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class DependencyProbe:
    ragas_installed: bool
    ragas_version: str | None
    rapidfuzz_installed: bool
    single_turn_import_path: str | None
    supported_metrics: dict[str, str]
    blockers: list[str]


@dataclass
class MetricSummary:
    name: str
    count: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    errors: int


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def load_queries(path: Path) -> tuple[list[QueryDefinition], int]:
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    if isinstance(raw, dict):
        if "queries" in raw:
            raw = raw["queries"]
        elif "samples" in raw:
            raw = raw["samples"]
        else:
            raw = list(raw.values())

    if not isinstance(raw, list):
        raise ValueError(f"Expected list-like query payload, got {type(raw).__name__}")

    queries: list[QueryDefinition] = []
    metadata_blocks = 0

    for idx, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            metadata_blocks += 1
            continue

        has_any_query_shape = any(
            key in item for key in ("query_id", "id", "user_input", "query")
        )
        if not has_any_query_shape:
            metadata_blocks += 1
            continue

        query_id = str(item.get("query_id") or item.get("id") or f"_row_{idx}")
        user_input = str(item.get("user_input") or item.get("query") or "").strip()
        reference_raw = item.get("reference")
        reference = str(reference_raw).strip() if reference_raw else None

        queries.append(
            QueryDefinition(
                row_index=idx,
                query_id=query_id,
                has_query_id=bool(item.get("query_id") or item.get("id")),
                user_input=user_input,
                has_user_input=bool(user_input),
                persona=str(item.get("persona", "Unknown")),
                expected_query_type=str(
                    item.get("expected_query_type") or item.get("query_type") or "SEMANTIC"
                ),
                expected_document_family=str(
                    item.get("expected_document_family")
                    or item.get("document_family")
                    or ""
                ),
                reference=reference,
                reference_contexts=_normalize_string_list(item.get("reference_contexts")),
                expected_source_patterns=_normalize_string_list(
                    item.get("expected_source_patterns")
                ),
                has_ground_truth=bool(item.get("has_ground_truth", False)),
            )
        )

    return queries, metadata_blocks


def analyze_readiness(queries: list[QueryDefinition]) -> list[ReadinessRecord]:
    records: list[ReadinessRecord] = []
    for query in queries:
        reasons: list[str] = []

        if not query.has_query_id:
            reasons.append("missing_query_id")
        if not query.has_user_input:
            reasons.append("missing_user_input")
        if not query.reference_contexts:
            reasons.append("missing_reference_contexts")
        if not query.reference:
            reasons.append("missing_reference")

        eligible_for_retrieval_metrics = (
            query.has_user_input and bool(query.reference_contexts)
        )
        fully_phase2c_enriched = bool(query.reference and query.reference_contexts)

        records.append(
            ReadinessRecord(
                query_id=query.query_id,
                eligible_for_retrieval_metrics=eligible_for_retrieval_metrics,
                fully_phase2c_enriched=fully_phase2c_enriched,
                reasons=reasons,
            )
        )
    return records


def probe_dependencies() -> DependencyProbe:
    ragas_spec = importlib.util.find_spec("ragas")
    rapidfuzz_spec = importlib.util.find_spec("rapidfuzz")

    supported_metrics: dict[str, str] = {}
    blockers: list[str] = []
    ragas_version: str | None = None
    sample_import_path: str | None = None

    if ragas_spec is None:
        blockers.append("ragas_not_installed")
        return DependencyProbe(
            ragas_installed=False,
            ragas_version=None,
            rapidfuzz_installed=rapidfuzz_spec is not None,
            single_turn_import_path=None,
            supported_metrics=supported_metrics,
            blockers=blockers,
        )

    ragas = importlib.import_module("ragas")
    ragas_version = getattr(ragas, "__version__", "unknown")

    try:
        importlib.import_module("ragas").SingleTurnSample
        sample_import_path = "ragas.SingleTurnSample"
    except Exception:
        try:
            importlib.import_module("ragas.dataset_schema").SingleTurnSample
            sample_import_path = "ragas.dataset_schema.SingleTurnSample"
        except Exception:
            blockers.append("single_turn_sample_import_failed")

    try:
        metrics_module = importlib.import_module("ragas.metrics")
        if hasattr(metrics_module, "NonLLMContextRecall"):
            supported_metrics["nonllm_context_recall"] = (
                "ragas.metrics.NonLLMContextRecall"
            )
        else:
            blockers.append("nonllm_context_recall_metric_missing")

        if hasattr(metrics_module, "NonLLMContextPrecisionWithReference"):
            supported_metrics["nonllm_context_precision_with_reference"] = (
                "ragas.metrics.NonLLMContextPrecisionWithReference"
            )
        else:
            blockers.append("nonllm_context_precision_metric_missing")
    except Exception:
        blockers.append("ragas_metrics_import_failed")

    if rapidfuzz_spec is None:
        blockers.append("rapidfuzz_not_installed")

    return DependencyProbe(
        ragas_installed=True,
        ragas_version=ragas_version,
        rapidfuzz_installed=rapidfuzz_spec is not None,
        single_turn_import_path=sample_import_path,
        supported_metrics=supported_metrics,
        blockers=blockers,
    )


def print_readiness_summary(
    queries: list[QueryDefinition],
    readiness: list[ReadinessRecord],
    metadata_blocks: int,
    query_path: Path,
) -> None:
    total = len(queries)
    eligible = sum(1 for r in readiness if r.eligible_for_retrieval_metrics)
    phase2c_ready = sum(1 for r in readiness if r.fully_phase2c_enriched)
    reason_counts = Counter(reason for r in readiness for reason in r.reasons)
    per_type_ready = Counter(
        q.expected_query_type
        for q, r in zip(queries, readiness, strict=True)
        if r.eligible_for_retrieval_metrics
    )

    print("=" * 72)
    print("  RAGAS READINESS ANALYSIS")
    print("=" * 72)
    print(f"Query file: {query_path.name}")
    print(f"Loaded query rows: {total}")
    print(f"Skipped metadata blocks: {metadata_blocks}")
    print(f"Eligible now for retrieval-side RAGAS metrics: {eligible}/{total}")
    print(f"Fully Phase 2C enriched (reference + reference_contexts): {phase2c_ready}/{total}")
    print(f"Blocked on Phase 2C enrichment: {total - phase2c_ready}/{total}")
    print()
    print("Skipped / incomplete counts by reason:")
    for reason, count in sorted(reason_counts.items()):
        print(f"  - {reason}: {count}")
    print()
    print("Eligible subset by expected_query_type:")
    for query_type, count in sorted(per_type_ready.items()):
        print(f"  - {query_type}: {count}")
    print()


def print_dependency_summary(probe: DependencyProbe) -> None:
    print("=" * 72)
    print("  DEPENDENCY PROBE")
    print("=" * 72)
    print(f"ragas installed: {'yes' if probe.ragas_installed else 'no'}")
    print(f"ragas version: {probe.ragas_version or 'n/a'}")
    print(f"rapidfuzz installed: {'yes' if probe.rapidfuzz_installed else 'no'}")
    print(f"SingleTurnSample import path: {probe.single_turn_import_path or 'n/a'}")
    print("Supported metric imports:")
    if probe.supported_metrics:
        for name, path in sorted(probe.supported_metrics.items()):
            print(f"  - {name}: {path}")
    else:
        print("  - none")
    if probe.blockers:
        print("Execution blockers:")
        for blocker in probe.blockers:
            print(f"  - {blocker}")
    else:
        print("Execution blockers: none")
    print()


def _build_pipeline(top_k: int):
    sys.path.insert(0, str(REPO_ROOT))

    import torch  # noqa: WPS433

    from src.config.schema import load_config  # noqa: WPS433
    from src.llm.client import LLMClient  # noqa: WPS433
    from src.query.context_builder import ContextBuilder  # noqa: WPS433
    from src.query.embedder import Embedder  # noqa: WPS433
    from src.query.pipeline import QueryPipeline  # noqa: WPS433
    from src.query.query_router import QueryRouter  # noqa: WPS433
    from src.query.vector_retriever import VectorRetriever  # noqa: WPS433
    from src.store.lance_store import LanceStore  # noqa: WPS433

    config = load_config(str(REPO_ROOT / "config" / "config.yaml"))
    store = LanceStore(str(REPO_ROOT / config.paths.lance_db))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device=device,
    )
    retriever = VectorRetriever(store, embedder, top_k=top_k)
    ctx_builder = ContextBuilder(
        top_k=top_k,
        reranker_enabled=config.retrieval.reranker_enabled,
    )
    llm_client = LLMClient()
    router = QueryRouter(llm_client)

    entity_retriever = None
    entity_db_path = REPO_ROOT / config.paths.entity_db
    if entity_db_path.exists():
        try:
            from src.query.entity_retriever import EntityRetriever  # noqa: WPS433
            from src.store.entity_store import EntityStore  # noqa: WPS433
            from src.store.relationship_store import RelationshipStore  # noqa: WPS433

            entity_retriever = EntityRetriever(
                EntityStore(str(entity_db_path)),
                RelationshipStore(str(entity_db_path)),
            )
        except Exception:
            entity_retriever = None

    pipeline = QueryPipeline(
        router=router,
        vector_retriever=retriever,
        entity_retriever=entity_retriever,
        context_builder=ctx_builder,
        generator=None,
        crag_verifier=None,
    )
    return pipeline, {
        "device": device,
        "store_chunks": store.count(),
        "router_provider": llm_client.provider if llm_client.available else "fallback",
    }


def _load_single_turn_sample_class():
    ragas = importlib.import_module("ragas")
    if hasattr(ragas, "SingleTurnSample"):
        return ragas.SingleTurnSample
    return importlib.import_module("ragas.dataset_schema").SingleTurnSample


def _instantiate_metric(metric_path: str):
    module_name, class_name = metric_path.rsplit(".", 1)
    metric_cls = getattr(importlib.import_module(module_name), class_name)
    return metric_cls()


def _extract_metric_value(result: Any) -> float:
    if hasattr(result, "value"):
        return float(result.value)
    return float(result)


def _score_metric(metric: Any, sample: Any, sample_kwargs: dict[str, Any]) -> float:
    if hasattr(metric, "single_turn_score"):
        return _extract_metric_value(metric.single_turn_score(sample))

    if hasattr(metric, "single_turn_ascore"):
        return _extract_metric_value(asyncio.run(metric.single_turn_ascore(sample)))

    if hasattr(metric, "score"):
        return _extract_metric_value(metric.score(**sample_kwargs))

    if hasattr(metric, "ascore"):
        return _extract_metric_value(asyncio.run(metric.ascore(**sample_kwargs)))

    raise RuntimeError(f"Unsupported metric interface: {metric!r}")


def _retrieved_contexts_from_query(
    pipeline: Any,
    query_text: str,
    top_k: int,
) -> list[str]:
    classification, _context, _stage_timings = pipeline.retrieve_context(query_text, top_k=top_k)
    search_query = classification.expanded_query or query_text
    raw_results = pipeline.vector_retriever.search(search_query, top_k=top_k)

    contexts: list[str] = []
    seen: set[str] = set()
    for result in raw_results:
        text = _clean_text(result.enriched_text or result.text)
        if not text or text in seen:
            continue
        seen.add(text)
        contexts.append(text)
    return contexts


def _summarize_metric(name: str, values: list[float], errors: int) -> MetricSummary:
    if not values:
        return MetricSummary(
            name=name,
            count=0,
            mean=None,
            median=None,
            minimum=None,
            maximum=None,
            errors=errors,
        )
    return MetricSummary(
        name=name,
        count=len(values),
        mean=statistics.fmean(values),
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
        errors=errors,
    )


def execute_metrics(
    queries: list[QueryDefinition],
    readiness: list[ReadinessRecord],
    probe: DependencyProbe,
    top_k: int,
    limit: int | None,
) -> tuple[list[MetricSummary], Counter[str]]:
    if not probe.ragas_installed:
        raise RuntimeError("ragas_not_installed")

    supported_paths = dict(probe.supported_metrics)
    if not probe.rapidfuzz_installed:
        supported_paths.pop("nonllm_context_precision_with_reference", None)

    if not supported_paths:
        raise RuntimeError("no_supported_metrics_available")

    SingleTurnSample = _load_single_turn_sample_class()
    pipeline, pipeline_info = _build_pipeline(top_k=top_k)

    print("=" * 72)
    print("  EXECUTION CONTEXT")
    print("=" * 72)
    print(f"Store chunks: {pipeline_info['store_chunks']:,}")
    print(f"Embedder device: {pipeline_info['device']}")
    print(f"Router provider: {pipeline_info['router_provider']}")
    print()

    metric_values: dict[str, list[float]] = defaultdict(list)
    metric_errors: Counter[str] = Counter()
    skip_reasons: Counter[str] = Counter()

    eligible_pairs = [
        (query, record)
        for query, record in zip(queries, readiness, strict=True)
        if record.eligible_for_retrieval_metrics
    ]
    if limit is not None:
        eligible_pairs = eligible_pairs[:limit]

    for query, _record in eligible_pairs:
        try:
            retrieved_contexts = _retrieved_contexts_from_query(
                pipeline=pipeline,
                query_text=query.user_input,
                top_k=top_k,
            )
        except Exception:
            skip_reasons["retrieval_execution_failed"] += 1
            continue

        if not retrieved_contexts:
            skip_reasons["no_retrieved_contexts"] += 1
            continue

        sample_kwargs = {
            "user_input": query.user_input,
            "retrieved_contexts": retrieved_contexts,
            "reference_contexts": query.reference_contexts,
        }
        if query.reference:
            sample_kwargs["reference"] = query.reference

        sample = SingleTurnSample(**sample_kwargs)

        for metric_name, metric_path in supported_paths.items():
            try:
                metric = _instantiate_metric(metric_path)
                score = _score_metric(metric=metric, sample=sample, sample_kwargs=sample_kwargs)
                metric_values[metric_name].append(score)
            except Exception:
                metric_errors[metric_name] += 1

    summaries = [
        _summarize_metric(name, metric_values.get(name, []), metric_errors.get(name, 0))
        for name in sorted(supported_paths)
    ]
    return summaries, skip_reasons


def print_metric_summaries(
    summaries: list[MetricSummary],
    skip_reasons: Counter[str],
    evaluated_limit: int | None,
) -> None:
    print("=" * 72)
    print("  METRIC OUTPUT")
    print("=" * 72)
    if evaluated_limit is not None:
        print(f"Evaluation limit applied: {evaluated_limit}")
    for summary in summaries:
        print(f"- {summary.name}")
        print(f"    count={summary.count}")
        print(f"    mean={summary.mean if summary.mean is not None else 'n/a'}")
        print(f"    median={summary.median if summary.median is not None else 'n/a'}")
        print(f"    min={summary.minimum if summary.minimum is not None else 'n/a'}")
        print(f"    max={summary.maximum if summary.maximum is not None else 'n/a'}")
        print(f"    errors={summary.errors}")
    if skip_reasons:
        print("Sample skips during execution:")
        for reason, count in sorted(skip_reasons.items()):
            print(f"  - {reason}: {count}")
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only RAGAS readiness + execution runner for HybridRAG V2",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=DEFAULT_QUERIES,
        help="Path to the production query JSON",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Top-K retrieval depth for retrieved_contexts",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on eligible queries to evaluate",
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Only analyze readiness; skip dependency-gated execution",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queries, metadata_blocks = load_queries(args.queries)
    readiness = analyze_readiness(queries)
    probe = probe_dependencies()

    print_readiness_summary(queries, readiness, metadata_blocks, args.queries)
    print_dependency_summary(probe)

    if args.analysis_only:
        return 0

    if not probe.ragas_installed:
        print("RAGAS execution blocked: ragas is not installed in the project venv.")
        return 2

    try:
        summaries, skip_reasons = execute_metrics(
            queries=queries,
            readiness=readiness,
            probe=probe,
            top_k=args.top_k,
            limit=args.limit,
        )
    except RuntimeError as exc:
        print(f"RAGAS execution blocked: {exc}")
        return 2

    print_metric_summaries(
        summaries=summaries,
        skip_reasons=skip_reasons,
        evaluated_limit=args.limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
