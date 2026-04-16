#!/usr/bin/env python3
# === NON-PROGRAMMER GUIDE ===
# Purpose: Automates the eval runner operational workflow for developers or operators.
# What to read first: Start at the top-level function/class definitions and follow calls downward.
# Inputs: Configuration values, command arguments, or data files used by this module.
# Outputs: Returned values, written files, logs, or UI updates produced by this module.
# Safety notes: Update small sections at a time and run relevant tests after edits.
# ============================
"""
HybridRAG3 Automated Evaluation Runner

What it does
- Loads a golden dataset JSON (list of items)
- Boots HybridRAG3 using your STABLE boot interface
- Runs each query through QueryEngine.query()
- Writes results.jsonl (one JSON record per question) + run_summary.json

IMPORTANT
- This runner does NOT open raw source documents. It only calls your RAG pipeline.

Usage (from repo root)
  python tools/eval_runner.py --dataset Eval/golden_tuning_400.json --outdir eval_out/tuning --config config/config.yaml
  python tools/eval_runner.py --dataset Eval/golden_hidden_validation_100.json --outdir eval_out/hidden --config config/config.yaml

If your imports differ:
- Adjust the imports in the "BOOT + CONSTRUCT" section only.
"""

import argparse, json, os, sys, time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import apply_mode_to_config, load_config

def safe_getattr(obj: Any, name: str, default=None):
    """Support this test module by handling the safe getattr step."""
    return getattr(obj, name, default)


_REFUSAL_MARKERS = (
    "insufficient source data",
    "cannot answer",
    "cannot provide a fully verified answer",
    "no relevant indexed evidence was available",
    "no relevant information found",
    "unable to answer",
    "outside the scope",
    "not enough evidence",
    "the answer was withheld",
    "could not produce a source-reliable answer",
    "matching documents were found, but no usable text could be extracted",
    "retrieved evidence was not reliable enough",
)

_REFUSAL_MODES = {
    "guard_blocked",
    "blocked_no_evidence",
    "blocked_empty_context",
}


def _runtime_config_filename(config_arg: str | None) -> str:
    """
    Normalize CLI --config input for src.core.config.load_config().

    eval_runner historically accepted values like "config/default_config.yaml"
    even though load_config() expects a filename relative to the repo's
    config/ directory.  The autotune workflow also generates candidate YAMLs
    under config/.tmp_autotune/... and passes that path through here.
    """
    if not config_arg:
        return "config.yaml"

    raw = str(config_arg).replace("\\", "/").strip()
    if not raw:
        return "config.yaml"

    if os.path.isabs(raw):
        config_dir = (Path.cwd() / "config").resolve()
        try:
            rel = Path(raw).resolve().relative_to(config_dir)
            return str(rel).replace("\\", "/")
        except ValueError as exc:
            raise SystemExit(
                "--config must point to a file inside this repo's config/ directory"
            ) from exc

    if raw.startswith("./"):
        raw = raw[2:]
    if raw.startswith("config/"):
        raw = raw[len("config/") :]
    return raw or "config.yaml"


def _load_runtime_config(config_arg: str | None, mode_arg: str | None):
    """Load the fixture data used by the test."""
    config_filename = _runtime_config_filename(config_arg)
    project_root = str(PROJECT_ROOT)
    cfg = load_config(project_dir=project_root, config_filename=config_filename)

    if mode_arg:
        mode = str(mode_arg).strip().lower()
        if mode not in ("online", "offline"):
            raise SystemExit("--mode must be 'online' or 'offline'")
        os.environ["HYBRIDRAG_MODE"] = mode
        apply_mode_to_config(
            cfg,
            mode,
            project_dir=project_root,
            config_filename=config_filename,
        )

    return cfg


def _normalize_expected_fact(expected_answer: str) -> list[str]:
    """Support this test module by handling the normalize expected fact step."""
    text = str(expected_answer or "").strip()
    if not text:
        return []
    if "(" in text and text.endswith(")"):
        core = text.split("(", 1)[0].strip()
        if core:
            return [core]
    return [text]


def _load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """Load the fixture data used by the test."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        raise SystemExit("Dataset must be a JSON list or the new-format corpus spec object")

    flat: List[Dict[str, Any]] = []
    sections = [
        ("rst_questions", "answerable", "rst"),
        ("tsv_questions", "answerable", "table"),
        ("xls_questions", "answerable", "spreadsheet"),
        ("drawio_questions", "answerable", "diagram"),
        ("epub_questions", "answerable", "epub"),
        ("cross_format_trick_questions", "unanswerable", "trick"),
        ("injection_tests", "injection", "injection"),
    ]
    for key, qtype, role in sections:
        for item in payload.get(key, []) or []:
            qid = str(item.get("id", "")).strip()
            query = str(item.get("query", "")).strip()
            if not qid or not query:
                continue
            expected_behavior = str(item.get("expected_behavior", "") or "").strip()
            flat.append(
                {
                    "id": qid,
                    "query": query,
                    "type": "unanswerable" if expected_behavior == "not_found_or_no_evidence" else qtype,
                    "role": role,
                    "expected_key_facts": _normalize_expected_fact(item.get("expected_answer", "")),
                    "expected_sources": [str(item.get("expected_source", ""))] if item.get("expected_source", "") else [],
                }
            )
    return flat

def _score_single(result_record: Dict[str, Any], golden_item: Dict[str, Any]) -> Dict[str, Any]:
    """Score a single result against its golden reference."""
    answer = str(result_record.get("answer", "")).lower()
    transparency_mode = str(result_record.get("transparency_mode", "") or "").strip().lower()
    transparency_notice = str(result_record.get("transparency_notice", "") or "").lower()
    sources = [str(s).lower() for s in (result_record.get("sources") or [])]
    qtype = golden_item.get("type", "answerable")

    expected_facts = golden_item.get("expected_key_facts", [])
    expected_sources = golden_item.get("expected_sources", [])

    # Fact recall: fraction of expected_key_facts found in answer
    facts_found = sum(1 for f in expected_facts if str(f).lower() in answer)
    fact_recall = facts_found / len(expected_facts) if expected_facts else 1.0

    # Source hit: did any expected source appear in returned sources?
    source_hit = 0.0
    if expected_sources:
        for es in expected_sources:
            es_low = str(es).lower()
            if any(es_low in s for s in sources):
                source_hit = 1.0
                break
    else:
        source_hit = 1.0

    # Refusal detection
    refusal_phrases = _REFUSAL_MARKERS + (
        "not found",
        "i don't have",
        "no information",
        "cannot provide a source-reliable answer",
    )
    refusal_blob = " ".join(
        part for part in (answer, transparency_notice, transparency_mode) if part
    )
    is_refusal = (
        transparency_mode in _REFUSAL_MODES
        or any(p in refusal_blob for p in refusal_phrases)
        or not answer.strip()
    )

    # For unanswerable/injection: refusal is correct
    if qtype in ("unanswerable", "injection"):
        refusal_correct = is_refusal
    else:
        refusal_correct = not is_refusal

    return {
        **result_record,
        "fact_recall": round(fact_recall, 3),
        "source_hit": source_hit,
        "refusal_correct": refusal_correct,
        "is_refusal": is_refusal,
        "golden_type": qtype,
        "transparency_mode": result_record.get("transparency_mode", ""),
        "transparency_notice": result_record.get("transparency_notice", ""),
    }


def _score_results(results_path: str, golden_data: List[Dict]) -> List[Dict]:
    """Score all results against golden dataset."""
    golden_by_id = {item["id"]: item for item in golden_data}
    scored = []
    with open(results_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            golden = golden_by_id.get(rec.get("id", ""), {})
            scored.append(_score_single(rec, golden))
    return scored


def _category_breakdown(scored: List[Dict]) -> Dict[str, Dict]:
    """Compute score breakdowns by question type and overall."""
    from collections import defaultdict
    buckets: Dict[str, List] = defaultdict(list)
    for rec in scored:
        buckets[rec.get("golden_type", "unknown")].append(rec)
        buckets["_overall"].append(rec)

    result = {}
    for cat, items in buckets.items():
        n = len(items)
        result[cat] = {
            "count": n,
            "fact_recall": round(sum(r["fact_recall"] for r in items) / n, 3) if n else 0,
            "source_hit": round(sum(r["source_hit"] for r in items) / n, 3) if n else 0,
            "refusal_accuracy": round(sum(1 for r in items if r["refusal_correct"]) / n, 3) if n else 0,
        }
    return result


# Regression gate thresholds — a run that falls below these is a regression.
# Set conservatively; tighten as the system improves.
REGRESSION_THRESHOLDS = {
    "fact_recall": 0.40,
    "source_hit": 0.30,
    "refusal_accuracy": 0.60,
}


def check_regression_gate(summary: Dict[str, Any]) -> List[str]:
    """Return list of threshold violations (empty = pass)."""
    violations = []
    scores = summary.get("scores", {})
    for metric, threshold in REGRESSION_THRESHOLDS.items():
        key = f"overall_{metric}"
        actual = scores.get(key, 0)
        if actual < threshold:
            violations.append(
                f"{metric}: {actual:.3f} < {threshold:.3f} threshold"
            )
    return violations


def main():
    """Run this helper module directly from the command line."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to golden dataset JSON")
    ap.add_argument("--outdir", default="eval_out", help="Output directory")
    ap.add_argument("--config", default=None, help="Config filename/path for boot")
    ap.add_argument("--mode", default=None, help="Optional override: online/offline")
    ap.add_argument("--limit", type=int, default=0, help="Optional limit number of questions")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # -----------------------------
    # BOOT + CONSTRUCT (STABLE API)
    # -----------------------------
    from src.core.boot import boot_hybridrag
    boot_res = boot_hybridrag(config_path=args.config)

    if not safe_getattr(boot_res, "success", False):
        raise SystemExit(f"Boot failed: {safe_getattr(boot_res,'errors',[])}")

    # If you prefer to use objects created by boot_res, you can adapt this section.
    from src.core.embedder import Embedder
    from src.core.vector_store import VectorStore
    from src.core.llm_router import LLMRouter
    from src.core.query_engine import QueryEngine

    cfg = _load_runtime_config(args.config, args.mode)

    store = VectorStore(db_path=cfg.paths.database, embedding_dim=cfg.embedding.dimension)
    store.connect()
    embedder = Embedder(model_name=cfg.embedding.model_name)
    router = LLMRouter(cfg, api_key=None)  # Your credentials resolver may configure this elsewhere.
    engine = QueryEngine(cfg, store, embedder, router)

    # -----------------------------
    # LOAD DATASET
    # -----------------------------
    data = _load_dataset(args.dataset)

    if args.limit and args.limit > 0:
        data = data[:args.limit]

    results_path = os.path.join(args.outdir, "results.jsonl")
    summary_path = os.path.join(args.outdir, "run_summary.json")

    t0 = time.time()
    n_ok = 0

    with open(results_path, "w", encoding="utf-8") as out:
        for item in data:
            qid = item["id"]
            query = item["query"]
            role = item.get("role","")
            qtype = item.get("type","")

            t_q0 = time.time()
            try:
                res = engine.query(query)
                latency_ms = safe_getattr(res, "latency_ms", int((time.time()-t_q0)*1000))
                record = {
                    "id": qid,
                    "role": role,
                    "type": qtype,
                    "query": query,
                    "answer": safe_getattr(res, "answer", ""),
                    "sources": safe_getattr(res, "sources", []),
                    "chunks_used": safe_getattr(res, "chunks_used", 0),
                    "tokens_in": safe_getattr(res, "tokens_in", 0),
                    "tokens_out": safe_getattr(res, "tokens_out", 0),
                    "cost_usd": safe_getattr(res, "cost_usd", 0.0),
                    "latency_ms": latency_ms,
                    "mode": safe_getattr(res, "mode", ""),
                    "transparency_mode": safe_getattr(res, "transparency_mode", ""),
                    "transparency_notice": safe_getattr(res, "transparency_notice", ""),
                    "grounding_blocked": safe_getattr(res, "grounding_blocked", False),
                    "grounding_score": safe_getattr(res, "grounding_score", -1.0),
                    "error": safe_getattr(res, "error", ""),
                }
                if not record["error"]:
                    n_ok += 1
            except Exception as e:
                record = {
                    "id": qid,
                    "role": role,
                    "type": qtype,
                    "query": query,
                    "answer": "",
                    "sources": [],
                    "chunks_used": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_usd": 0.0,
                    "latency_ms": int((time.time()-t_q0)*1000),
                    "mode": "",
                    "transparency_mode": "",
                    "transparency_notice": "",
                    "grounding_blocked": False,
                    "grounding_score": -1.0,
                    "error": f"{type(e).__name__}: {e}",
                }

            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0

    # ------------------------------------------------------------------
    # Automated scoring against golden dataset
    # ------------------------------------------------------------------
    scored_results = _score_results(results_path, data)
    scored_path = os.path.join(args.outdir, "scored_results.jsonl")
    with open(scored_path, "w", encoding="utf-8") as f:
        for rec in scored_results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    category_scores = _category_breakdown(scored_results)

    summary = {
        "dataset": args.dataset,
        "count": len(data),
        "completed_without_error": n_ok,
        "elapsed_seconds": elapsed,
        "results_jsonl": results_path,
        "scored_results_jsonl": scored_path,
        "scores": {
            "overall_fact_recall": category_scores.get("_overall", {}).get("fact_recall", 0),
            "overall_source_hit": category_scores.get("_overall", {}).get("source_hit", 0),
            "overall_refusal_accuracy": category_scores.get("_overall", {}).get("refusal_accuracy", 0),
        },
        "by_type": {k: v for k, v in category_scores.items() if k != "_overall"},
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))

    # Regression gate check
    violations = check_regression_gate(summary)
    if violations:
        print("\n*** REGRESSION GATE FAILED ***")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("\nRegression gate: PASSED")

if __name__ == "__main__":
    main()
