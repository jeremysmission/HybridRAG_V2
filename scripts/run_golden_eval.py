"""
Golden evaluation runner for HybridRAG V2.

Runs the golden query suite against the live pipeline and scores routing,
retrieval, confidence, latency, and CRAG behavior.

Usage:
    python scripts/run_golden_eval.py                       # full eval
    python scripts/run_golden_eval.py --retrieval-only      # skip LLM
    python scripts/run_golden_eval.py --query GQ-005        # single query
    python scripts/run_golden_eval.py --compare results/sprint1_eval.json
    python scripts/run_golden_eval.py --retrieval-only --gate sprint6
"""
from __future__ import annotations
import argparse, json, logging, sys, time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.config.schema import load_config, V2Config
from src.store.lance_store import LanceStore
from src.query.embedder import Embedder
from src.query.vector_retriever import VectorRetriever
from src.query.context_builder import ContextBuilder
from src.query.query_router import QueryRouter

logger = logging.getLogger("golden_eval")
GOLDEN_PATH = V2_ROOT / "tests" / "golden_eval" / "golden_queries.json"
RESULTS_DIR = V2_ROOT / "tests" / "golden_eval" / "results"


@dataclass
class QueryScore:
    query_id: str
    query: str
    expected_type: str
    routed_type: str
    routing_correct: bool
    expected_facts: list[str]
    retrieval_facts_found: list[str]
    retrieval_facts_missing: list[str]
    retrieval_pass: bool
    generation_facts_found: list[str]
    generation_facts_missing: list[str]
    generation_pass: bool | None
    expected_confidence: str
    actual_confidence: str
    confidence_correct: bool | None
    crag_triggered: bool
    crag_retries: int
    latency_ms: int
    error: str = ""


@dataclass
class EvalSummary:
    run_id: str
    timestamp: str
    total_queries: int
    routing_correct: int
    retrieval_pass: int
    generation_pass: int
    confidence_correct: int
    crag_triggered: int
    avg_latency_ms: float
    retrieval_only: bool
    scores: list[dict] = field(default_factory=list)


def _resolve_gate_thresholds(
    total_queries: int,
    retrieval_only: bool,
    gate: str,
    min_retrieval_pass: int | None,
    min_generation_pass: int | None,
) -> tuple[str, int, int | None]:
    """
    Resolve pass/fail thresholds for the current run.

    Defaults are intentionally pragmatic:
      - Single-query runs require that one query to pass.
      - Full 25-query retrieval-only runs default to the Sprint 6 floor (15/25).
      - All other runs default to strict all-pass unless the caller overrides.
    """
    if total_queries <= 0:
        return "all", 0, None

    if min_retrieval_pass is not None or min_generation_pass is not None:
        retrieval_floor = min_retrieval_pass if min_retrieval_pass is not None else total_queries
        generation_floor = min_generation_pass
        if generation_floor is not None and retrieval_only:
            generation_floor = None
        return "custom", min(total_queries, retrieval_floor), generation_floor

    if gate == "auto":
        if total_queries == 1:
            gate = "all"
        elif retrieval_only and total_queries == 25:
            gate = "sprint6"
        else:
            gate = "all"

    if gate == "sprint6":
        return "sprint6", min(total_queries, 15), None
    if gate == "sprint7":
        return "sprint7", min(total_queries, 20), None
    return "all", total_queries, (None if retrieval_only else total_queries)


def _init_pipeline(config: V2Config, retrieval_only: bool):
    """Initialize pipeline components. Returns tuple of all components."""
    store = LanceStore(str(V2_ROOT / config.paths.lance_db))
    if store.count() == 0:
        print("ERROR: No chunks in store. Run import_embedengine.py first.")
        sys.exit(1)
    print(f"  Store loaded: {store.count()} chunks")

    embedder = Embedder(model_name="nomic-ai/nomic-embed-text-v1.5", dim=768, device="cuda")
    retriever = VectorRetriever(store, embedder, top_k=config.retrieval.top_k)
    ctx_builder = ContextBuilder(
        top_k=config.retrieval.top_k,
        reranker_enabled=config.retrieval.reranker_enabled,
    )

    llm_client = router = generator = crag_verifier = entity_retriever = None

    if not retrieval_only:
        from src.llm.client import LLMClient
        from src.query.generator import Generator
        llm_client = LLMClient(
            api_base=config.llm.api_base, api_version=config.llm.api_version,
            model=config.llm.model, deployment=config.llm.deployment,
            max_tokens=config.llm.max_tokens, temperature=config.llm.temperature,
            timeout_seconds=config.llm.timeout_seconds,
        )
        if not llm_client.available:
            print("WARN: LLM client unavailable -- falling back to retrieval-only")
            retrieval_only = True
        else:
            router = QueryRouter(llm_client)
            generator = Generator(llm_client)
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
                    print("  Entity store loaded")
                except Exception as e:
                    logger.warning("Entity store init failed: %s", e)
            if config.crag.enabled:
                try:
                    from src.query.crag_verifier import CRAGVerifier
                    crag_verifier = CRAGVerifier(
                        config=config.crag, llm_client=llm_client,
                        vector_retriever=retriever, context_builder=ctx_builder,
                        generator=generator,
                    )
                    print("  CRAG verifier enabled")
                except Exception as e:
                    logger.warning("CRAG verifier init failed: %s", e)

    if router is None:
        from src.llm.client import LLMClient
        router = QueryRouter(LLMClient())  # no creds -> rule-based fallback
        print("  Router: rule-based fallback (no LLM)")

    return store, retriever, ctx_builder, router, generator, crag_verifier, entity_retriever, retrieval_only


def _check_facts(expected: list[str], text: str) -> tuple[list[str], list[str]]:
    """Check which expected facts appear (case-insensitive) in text."""
    lower = text.lower()
    found = [f for f in expected if f.lower() in lower]
    missing = [f for f in expected if f.lower() not in lower]
    return found, missing


def _run_single_query(qdef, router, retriever, ctx_builder, generator,
                      crag_verifier, entity_retriever, retrieval_only, config):
    """Run one golden query and return its score."""
    qid, query_text = qdef["id"], qdef["query"]
    expected_facts = qdef["expected_facts"]
    expected_confidence, expected_type = qdef["expected_confidence"], qdef["query_type"]
    start = time.time()
    error = ""
    try:
        classification = router.classify(query_text)
        routed_type = classification.query_type
        routing_correct = routed_type == expected_type

        search_query = classification.expanded_query or query_text
        results = retriever.search(search_query, top_k=config.retrieval.top_k)
        context = ctx_builder.build(results, query_text) if results else None
        context_text = context.context_text if context else ""
        ret_found, ret_missing = _check_facts(expected_facts, context_text)
        retrieval_pass = len(ret_missing) == 0

        gen_found, gen_missing = [], []
        generation_pass = None
        actual_confidence, crag_triggered, crag_retries = "N/A", False, 0

        if not retrieval_only and generator and context:
            try:
                from src.query.pipeline import QueryPipeline
                pipeline = QueryPipeline(
                    router=router, vector_retriever=retriever,
                    entity_retriever=entity_retriever, context_builder=ctx_builder,
                    generator=generator, crag_verifier=crag_verifier,
                )
                response = pipeline.query(query_text, top_k=config.retrieval.top_k)
                actual_confidence = response.confidence
                crag_triggered = response.crag_verified
                crag_retries = response.crag_retries
                gen_found, gen_missing = _check_facts(expected_facts, response.answer)
                generation_pass = len(gen_missing) == 0
            except Exception as e:
                error = f"generation: {e}"
                logger.error("Generation failed for %s: %s", qid, e)

        confidence_correct = None
        if actual_confidence != "N/A":
            confidence_correct = actual_confidence == expected_confidence

    except Exception as e:
        error = str(e)
        logger.error("Query %s failed: %s", qid, e)
        routed_type, routing_correct = "ERROR", False
        ret_found, ret_missing, retrieval_pass = [], expected_facts, False
        gen_found, gen_missing, generation_pass = [], [], None
        actual_confidence, confidence_correct = "ERROR", None
        crag_triggered, crag_retries = False, 0

    return QueryScore(
        query_id=qid, query=query_text, expected_type=expected_type,
        routed_type=routed_type, routing_correct=routing_correct,
        expected_facts=expected_facts,
        retrieval_facts_found=ret_found, retrieval_facts_missing=ret_missing,
        retrieval_pass=retrieval_pass,
        generation_facts_found=gen_found, generation_facts_missing=gen_missing,
        generation_pass=generation_pass,
        expected_confidence=expected_confidence, actual_confidence=actual_confidence,
        confidence_correct=confidence_correct,
        crag_triggered=crag_triggered, crag_retries=crag_retries,
        latency_ms=int((time.time() - start) * 1000), error=error,
    )


def _print_summary(scores: list[QueryScore], retrieval_only: bool) -> None:
    """Print formatted summary table to stdout."""
    sep = "-" * 100
    total = len(scores)
    print(f"\n{sep}\n  GOLDEN EVAL RESULTS\n{sep}")
    if retrieval_only:
        print(f"{'ID':<8} {'Route':>5} {'Retr':>5} {'Facts':>7} {'ms':>6}  Query")
    else:
        print(f"{'ID':<8} {'Route':>5} {'Retr':>5} {'Gen':>5} {'Conf':>5} {'CRAG':>5} {'ms':>6}  Query")
    print(sep)

    for s in scores:
        r = "PASS" if s.routing_correct else "FAIL"
        rv = "PASS" if s.retrieval_pass else "FAIL"
        f = f"{len(s.retrieval_facts_found)}/{len(s.expected_facts)}"
        q = s.query[:42] + ("..." if len(s.query) > 42 else "")
        if retrieval_only:
            print(f"{s.query_id:<8} {r:>5} {rv:>5} {f:>7} {s.latency_ms:>5}  {q}")
        else:
            g = "PASS" if s.generation_pass else ("FAIL" if s.generation_pass is False else " -- ")
            c = "PASS" if s.confidence_correct else ("FAIL" if s.confidence_correct is False else " -- ")
            cr = " YES" if s.crag_triggered else "  no"
            print(f"{s.query_id:<8} {r:>5} {rv:>5} {g:>5} {c:>5} {cr:>5} {s.latency_ms:>5}  {q}")

    rp = sum(1 for s in scores if s.routing_correct)
    ep = sum(1 for s in scores if s.retrieval_pass)
    al = sum(s.latency_ms for s in scores) / max(total, 1)
    print(sep)
    print(f"  Total: {total}  |  Routing: {rp}/{total} ({100*rp//max(total,1)}%)  |  Retrieval: {ep}/{total} ({100*ep//max(total,1)}%)")
    if not retrieval_only:
        gp = sum(1 for s in scores if s.generation_pass is True)
        gt = sum(1 for s in scores if s.generation_pass is not None)
        cp = sum(1 for s in scores if s.confidence_correct is True)
        ct = sum(1 for s in scores if s.confidence_correct is not None)
        cc = sum(1 for s in scores if s.crag_triggered)
        print(f"  Generation: {gp}/{gt}  |  Confidence: {cp}/{ct}  |  CRAG triggered: {cc}")
    print(f"  Avg latency: {al:.0f}ms\n{sep}")


def _print_comparison(current: EvalSummary, previous_path: str) -> None:
    """Load previous results and print side-by-side delta."""
    prev_file = Path(previous_path)
    if not prev_file.is_absolute():
        prev_file = RESULTS_DIR / prev_file
    if not prev_file.exists():
        print(f"WARN: Previous results not found: {prev_file}")
        return
    with open(prev_file, encoding="utf-8") as f:
        prev = json.load(f)

    sep = "=" * 80
    pt = prev.get("total_queries", 0)
    ct = current.total_queries

    def pct(v, t): return 100 * v / max(t, 1)
    def row(label, cv, pv):
        d = pct(cv, ct) - pct(pv, pt)
        return f"  {label:<16} {pct(cv,ct):5.0f}% ({cv}/{ct})   was {pct(pv,pt):5.0f}% ({pv}/{pt})   delta {d:+.0f}%"

    print(f"\n{sep}\n  COMPARISON: current vs previous\n{sep}")
    print(row("Routing", current.routing_correct, prev.get("routing_correct", 0)))
    print(row("Retrieval", current.retrieval_pass, prev.get("retrieval_pass", 0)))
    if not current.retrieval_only:
        print(row("Generation", current.generation_pass, prev.get("generation_pass", 0)))
        print(row("Confidence", current.confidence_correct, prev.get("confidence_correct", 0)))
    ap = prev.get("avg_latency_ms", 0)
    print(f"  {'Avg latency':<16} {current.avg_latency_ms:.0f}ms   was {ap:.0f}ms   delta {current.avg_latency_ms - ap:+.0f}ms")
    print(sep)

    # Per-query deltas
    prev_by_id = {s["query_id"]: s for s in prev.get("scores", [])}
    changes_found = False
    for cs in current.scores:
        ps = prev_by_id.get(cs["query_id"])
        if not ps:
            continue
        ch = []
        if cs["retrieval_pass"] != ps.get("retrieval_pass"):
            ch.append(f"retrieval {'FAIL' if ps.get('retrieval_pass') else 'PASS'}->{'PASS' if cs['retrieval_pass'] else 'FAIL'}")
        if cs.get("routing_correct") != ps.get("routing_correct"):
            ch.append(f"routing {'FAIL' if ps.get('routing_correct') else 'PASS'}->{'PASS' if cs.get('routing_correct') else 'FAIL'}")
        if ch:
            if not changes_found:
                print("\n  Per-query changes:")
                changes_found = True
            print(f"    {cs['query_id']}: {', '.join(ch)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="HybridRAG V2 golden evaluation runner")
    parser.add_argument("--config", default=str(V2_ROOT / "config" / "config.yaml"))
    parser.add_argument("--retrieval-only", action="store_true",
                        help="Skip LLM generation (routing + retrieval only, no API cost)")
    parser.add_argument("--gate", choices=["auto", "all", "sprint6", "sprint7"], default="auto",
                        help="Pass/fail gate. auto uses the Sprint 6 floor for full 25-query retrieval-only runs and strict all-pass otherwise.")
    parser.add_argument("--min-retrieval-pass", type=int, default=None,
                        help="Custom retrieval pass floor for exit status.")
    parser.add_argument("--min-generation-pass", type=int, default=None,
                        help="Custom generation pass floor for exit status (ignored in retrieval-only mode).")
    parser.add_argument("--query", type=str, default=None,
                        help="Run a single query by ID (e.g. GQ-001)")
    parser.add_argument("--compare", type=str, default=None,
                        help="Path to previous results JSON for side-by-side comparison")
    parser.add_argument("--output", type=str, default=None,
                        help="Output filename (default: sprint2_eval.json)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not GOLDEN_PATH.exists():
        print(f"ERROR: Golden queries not found at {GOLDEN_PATH}")
        sys.exit(1)
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden_queries = json.load(f)

    if args.query:
        golden_queries = [q for q in golden_queries if q["id"] == args.query]
        if not golden_queries:
            print(f"ERROR: Query '{args.query}' not found in golden set")
            sys.exit(1)

    print("=" * 60)
    print("  HybridRAG V2 -- Golden Evaluation")
    print(f"  Queries: {len(golden_queries)}  |  Mode: {'retrieval-only' if args.retrieval_only else 'full pipeline'}")
    print("=" * 60)

    config = load_config(args.config)
    (store, retriever, ctx_builder, router, generator,
     crag_verifier, entity_retriever, retrieval_only) = _init_pipeline(config, args.retrieval_only)
    print()

    scores: list[QueryScore] = []
    for i, qdef in enumerate(golden_queries, 1):
        print(f"  [{i}/{len(golden_queries)}] {qdef['id']}: {qdef['query'][:50]}...")
        score = _run_single_query(
            qdef, router, retriever, ctx_builder,
            generator, crag_verifier, entity_retriever, retrieval_only, config,
        )
        scores.append(score)
        st = "PASS" if score.retrieval_pass else "FAIL"
        print(f"           retr={st} facts={len(score.retrieval_facts_found)}/{len(score.expected_facts)} {score.latency_ms}ms")
        if score.error:
            print(f"           ERROR: {score.error}")

    _print_summary(scores, retrieval_only)

    gate_name, retrieval_floor, generation_floor = _resolve_gate_thresholds(
        total_queries=len(scores),
        retrieval_only=retrieval_only,
        gate=args.gate,
        min_retrieval_pass=args.min_retrieval_pass,
        min_generation_pass=args.min_generation_pass,
    )
    retrieval_pass_count = sum(1 for s in scores if s.retrieval_pass)
    generation_pass_count = sum(1 for s in scores if s.generation_pass is True)
    gate_pass = retrieval_pass_count >= retrieval_floor
    gate_bits = [f"retrieval>={retrieval_floor}/{len(scores)}"]
    if generation_floor is not None:
        gate_pass = gate_pass and generation_pass_count >= generation_floor
        gate_bits.append(f"generation>={generation_floor}/{len(scores)}")
    print(
        f"  Exit gate: {gate_name} ({', '.join(gate_bits)}) -> "
        f"{'PASS' if gate_pass else 'FAIL'}"
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    score_dicts = [asdict(s) for s in scores]
    summary = EvalSummary(
        run_id=run_id, timestamp=datetime.now(timezone.utc).isoformat(),
        total_queries=len(scores),
        routing_correct=sum(1 for s in scores if s.routing_correct),
        retrieval_pass=sum(1 for s in scores if s.retrieval_pass),
        generation_pass=sum(1 for s in scores if s.generation_pass is True),
        confidence_correct=sum(1 for s in scores if s.confidence_correct is True),
        crag_triggered=sum(1 for s in scores if s.crag_triggered),
        avg_latency_ms=sum(s.latency_ms for s in scores) / max(len(scores), 1),
        retrieval_only=retrieval_only, scores=score_dicts,
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = V2_ROOT / out_path
    else:
        out_path = RESULTS_DIR / "sprint3_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(asdict(summary), f, indent=2, default=str)
    print(f"\n  Results written to: {out_path}")

    latest_path = RESULTS_DIR / "latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(score_dicts, f, indent=2, default=str)
    print(f"  Latest results at:  {latest_path}")

    if args.compare:
        _print_comparison(summary, args.compare)

    store.close()
    sys.exit(0 if gate_pass else 1)


if __name__ == "__main__":
    main()
