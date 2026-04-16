"""
Golden eval runner — tests retrieval quality and (optionally) LLM generation.

Runs each golden query against the store, checks that expected facts
appear in retrieved chunks. If LLM credentials are configured, also
tests full generation and checks facts in the answer.

Usage:
  python tests/golden_eval/eval_runner.py
  python tests/golden_eval/eval_runner.py --config config/config.yaml
"""

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

v2_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(v2_root))

from src.config.schema import load_config
from src.store.lance_store import LanceStore
from src.query.embedder import Embedder
from src.query.vector_retriever import VectorRetriever
from src.query.context_builder import ContextBuilder
from src.query.generator import Generator
from src.llm.client import LLMClient


@dataclass
class EvalResult:
    """Result of evaluating a single golden query."""

    query_id: str
    query: str
    retrieval_pass: bool
    retrieval_facts_found: list[str]
    retrieval_facts_missing: list[str]
    generation_pass: bool | None  # None if LLM not available
    generation_facts_found: list[str]
    generation_facts_missing: list[str]
    confidence: str
    latency_ms: int


def check_facts(text: str, expected_facts: list[str]) -> tuple[list[str], list[str]]:
    """Check which expected facts appear in the text (case-insensitive)."""
    text_lower = text.lower()
    found = []
    missing = []
    for fact in expected_facts:
        if fact.lower() in text_lower:
            found.append(fact)
        else:
            missing.append(fact)
    return found, missing


def run_eval(config_path: str = "config/config.yaml") -> list[EvalResult]:
    """Run all golden queries and return results."""
    config = load_config(config_path)

    # Load golden queries
    queries_path = v2_root / "tests" / "golden_eval" / "golden_queries.json"
    with open(queries_path, encoding="utf-8-sig") as f:
        golden_queries = json.load(f)

    # Initialize pipeline
    store = LanceStore(str(v2_root / config.paths.lance_db))
    if store.count() == 0:
        print("ERROR: No chunks in store. Run import_embedengine.py first.")
        sys.exit(1)

    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )
    retriever = VectorRetriever(store, embedder, top_k=5)
    context_builder = ContextBuilder(top_k=5)

    # Try LLM
    llm_client = LLMClient(
        api_base=config.llm.api_base,
        model=config.llm.model,
        deployment=config.llm.deployment,
        temperature=config.llm.temperature,
    )
    generator = Generator(llm_client) if llm_client.available else None

    results = []

    for gq in golden_queries:
        start = time.time()

        # Retrieval
        search_results = retriever.search(gq["query"])
        all_chunk_text = " ".join(r.text for r in search_results)

        ret_found, ret_missing = check_facts(all_chunk_text, gq["expected_facts"])
        retrieval_pass = len(ret_missing) == 0

        # Generation (if LLM available)
        gen_pass = None
        gen_found = []
        gen_missing = []
        confidence = "N/A"

        if generator:
            try:
                context = context_builder.build(search_results, gq["query"])
                response = generator.generate(context, gq["query"])
                gen_found, gen_missing = check_facts(response.answer, gq["expected_facts"])
                gen_pass = len(gen_missing) == 0
                confidence = response.confidence
            except Exception as e:
                gen_pass = False
                gen_missing = gq["expected_facts"]
                confidence = f"ERROR: {e}"

        latency_ms = int((time.time() - start) * 1000)

        results.append(EvalResult(
            query_id=gq["id"],
            query=gq["query"],
            retrieval_pass=retrieval_pass,
            retrieval_facts_found=ret_found,
            retrieval_facts_missing=ret_missing,
            generation_pass=gen_pass,
            generation_facts_found=gen_found,
            generation_facts_missing=gen_missing,
            confidence=confidence,
            latency_ms=latency_ms,
        ))

    store.close()
    return results


def print_results(results: list[EvalResult]) -> None:
    """Print eval results as a table."""
    print()
    print("=" * 70)
    print("  HybridRAG V2 — Golden Eval Results")
    print("=" * 70)

    retrieval_passed = sum(1 for r in results if r.retrieval_pass)
    gen_tested = [r for r in results if r.generation_pass is not None]
    gen_passed = sum(1 for r in gen_tested if r.generation_pass)

    for r in results:
        ret_status = "PASS" if r.retrieval_pass else "FAIL"
        gen_status = "PASS" if r.generation_pass else ("FAIL" if r.generation_pass is False else "SKIP")

        print(f"\n  {r.query_id}: {r.query}")
        print(f"    Retrieval: {ret_status} ({len(r.retrieval_facts_found)}/{len(r.retrieval_facts_found) + len(r.retrieval_facts_missing)} facts)")
        if r.retrieval_facts_missing:
            print(f"      Missing: {r.retrieval_facts_missing}")
        print(f"    Generation: {gen_status} | Confidence: {r.confidence} | {r.latency_ms}ms")
        if r.generation_facts_missing:
            print(f"      Missing: {r.generation_facts_missing}")

    print()
    print("-" * 70)
    print(f"  Retrieval: {retrieval_passed}/{len(results)} passed")
    if gen_tested:
        print(f"  Generation: {gen_passed}/{len(gen_tested)} passed")
    else:
        print(f"  Generation: SKIPPED (no LLM credentials configured)")
    print("=" * 70)


def save_results(results: list[EvalResult]) -> None:
    """Save results to JSON for tracking."""
    output = []
    for r in results:
        output.append({
            "query_id": r.query_id,
            "query": r.query,
            "retrieval_pass": r.retrieval_pass,
            "retrieval_facts_found": r.retrieval_facts_found,
            "retrieval_facts_missing": r.retrieval_facts_missing,
            "generation_pass": r.generation_pass,
            "generation_facts_found": r.generation_facts_found,
            "generation_facts_missing": r.generation_facts_missing,
            "confidence": r.confidence,
            "latency_ms": r.latency_ms,
        })

    results_path = v2_root / "tests" / "golden_eval" / "results" / "latest.json"
    with open(results_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(output, f, indent=2)
        f.write("\n")
    print(f"\n  Results saved to: {results_path}")


def main():
    """Run this helper module directly from the command line."""
    import argparse
    parser = argparse.ArgumentParser(description="Golden eval runner")
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    results = run_eval(args.config)
    print_results(results)
    save_results(results)


if __name__ == "__main__":
    main()
