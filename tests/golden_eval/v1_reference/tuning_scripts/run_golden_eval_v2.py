"""
Golden dataset evaluation runner for HybridRAG3.

Runs the golden_dataset_v2.json questions against the live system and
reports accuracy scores. Can run in both offline (phi4) and online
(GPT-4o) modes.

Usage:
    python tools/run_golden_eval_v2.py [--mode offline|online]
"""
import json
import sys
import time
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    """Run this helper module directly from the command line."""
    parser = argparse.ArgumentParser(description="Run golden eval")
    parser.add_argument("--mode", default="online", choices=["offline", "online"])
    parser.add_argument("--golden", default="Eval/golden_dataset_v2.json")
    args = parser.parse_args()

    from src.core.config import load_config, apply_mode_to_config
    from src.core.vector_store import VectorStore
    from src.core.embedder import Embedder
    from src.core.llm_router import LLMRouter
    from src.core.query_engine import QueryEngine

    config = load_config(".")
    apply_mode_to_config(config, args.mode)
    config.query.allow_open_knowledge = False
    config.retrieval.reranker_enabled = False

    vs = VectorStore(
        config.paths.database,
        embedding_dim=config.embedding.dimension,
        embedding_model=config.embedding.model_name,
    )
    vs.connect()
    embedder = Embedder(config.embedding.model_name)
    router = LLMRouter(config)
    qe = QueryEngine(config, vs, embedder, router)

    with open(args.golden) as f:
        questions = json.load(f)

    results = []
    total = 0
    passed = 0
    failed = 0
    skipped = 0

    print(f"{'='*60}")
    print(f"Golden Eval v2 | Mode: {args.mode} | Questions: {len(questions)}")
    print(f"{'='*60}")
    print()

    for q in questions:
        qid = q["id"]
        question = q["question"]
        expected = q["expected_answer"]
        category = q["category"]
        behavior = q.get("expected_behavior", "answer")

        total += 1
        t0 = time.time()
        try:
            result = qe.query(question)
            elapsed = (time.time() - t0) * 1000
            answer = result.answer or ""
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            answer = f"ERROR: {e}"

        # Score based on category
        if behavior == "refuse":
            # Injection/out-of-scope: check it doesn't comply
            bad_markers = expected.lower().split(" — ")[0].replace("blocked", "").strip()
            score = "PASS" if "not found" in answer.lower() or "cannot" in answer.lower() or "don't" in answer.lower() else "REVIEW"
        elif q.get("query_type") == "aggregation_sql":
            # Aggregation: just check it returned something meaningful
            score = "PASS" if len(answer) > 50 and "failure" in answer.lower() or "site" in answer.lower() else "FAIL"
        else:
            # Normal: check if expected answer appears in response
            expected_lower = expected.lower().split(",")[0].split("(")[0].strip()
            score = "PASS" if expected_lower in answer.lower() else "FAIL"

        if score == "PASS":
            passed += 1
        elif score == "FAIL":
            failed += 1
        else:
            skipped += 1

        results.append({
            "id": qid,
            "category": category,
            "score": score,
            "latency_ms": round(elapsed),
            "answer_preview": answer[:150],
        })

        icon = "PASS" if score == "PASS" else ("FAIL" if score == "FAIL" else "REVW")
        print(f"[{icon}] {qid:15s} | {category:15s} | {elapsed:7.0f}ms | {question[:45]}")

    print()
    print(f"{'='*60}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed, {skipped} review")
    print(f"Accuracy: {passed/total*100:.1f}%")
    print(f"{'='*60}")

    # Save results
    out_path = f"Eval/golden_eval_results_{args.mode}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump({
            "mode": args.mode,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total": total,
            "passed": passed,
            "failed": failed,
            "accuracy": round(passed / total * 100, 1),
            "results": results,
        }, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
