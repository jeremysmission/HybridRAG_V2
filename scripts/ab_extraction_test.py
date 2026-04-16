"""
A/B Extraction Quality Test — phi4:14b vs GPT-4o.

Sprint 5A: Validates whether phi4:14b (free, local) can match GPT-4o extraction
quality before committing production resources.

Pulls diverse sample chunks from Clone1 index (V1 production data),
runs both extractors, compares quality metrics side-by-side.

Usage:
  python scripts/ab_extraction_test.py
  python scripts/ab_extraction_test.py --sample-size 20 --clone1-db path/to/hybridrag.sqlite3
  python scripts/ab_extraction_test.py --report-only results/ab_test_latest.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.schema import load_config
from src.llm.client import LLMClient
from src.extraction.entity_extractor import EntityExtractor, ENTITY_SCHEMA, EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _default_clone1_db() -> str:
    """Resolve the default Clone1 SQLite path from the operator's home dir.

    Historical note: an earlier revision of this file used a raw-string
    literal ``r"{USER_HOME}\\HybridRAG3_Clone1\\..."`` that was never
    substituted by any templating step, so the script would hard-fail at
    startup on every machine with "Clone1 database not found at
    {USER_HOME}\\...". Same defect class as the one fixed in
    ``scripts/overnight_extraction.py`` (commit da7e5e5). Use
    ``Path.home()`` so the default resolves correctly on any Windows
    user profile, and let ``--clone1-db`` override it when the Clone1
    index lives somewhere else.
    """
    return str(Path.home() / "HybridRAG3_Clone1" / "data" / "index" / "hybridrag.sqlite3")


DEFAULT_CLONE1_DB = _default_clone1_db()
SAMPLE_SIZE = 50
CATEGORIES = {
    "short": "text_length < 300",
    "medium": "text_length BETWEEN 300 AND 1000",
    "long": "text_length > 1000",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ChunkSample:
    """Structured input record that keeps one unit of work easy to pass around and inspect."""
    chunk_id: str
    text: str
    source_path: str
    text_length: int
    category: str  # short/medium/long/ocr/tabular


@dataclass
class ExtractionMetrics:
    """Structured helper object used by the ab extraction test workflow."""
    model_name: str
    chunk_id: str
    entity_count: int = 0
    relationship_count: int = 0
    table_row_count: int = 0
    entity_types: dict = field(default_factory=dict)
    avg_confidence: float = 0.0
    json_valid: bool = True
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""


@dataclass
class ComparisonResult:
    """Small structured record used to keep related results together as the workflow runs."""
    chunk_id: str
    category: str
    text_preview: str
    phi4: ExtractionMetrics = None
    gpt4o: ExtractionMetrics = None
    entity_count_delta: int = 0
    relationship_count_delta: int = 0
    phi4_unique_entities: list = field(default_factory=list)
    gpt4o_unique_entities: list = field(default_factory=list)
    common_entities: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def sample_chunks(db_path: str, n: int = SAMPLE_SIZE) -> list[ChunkSample]:
    """
    Pull diverse sample from Clone1 index.

    Uses rowid-based random sampling (fast) instead of ORDER BY RANDOM()
    which does a full table scan on 27.6M rows (75GB, minutes to hours).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get max rowid for fast random sampling
    cur.execute("SELECT MAX(rowid) FROM chunks")
    max_rowid = cur.fetchone()[0] or 1

    samples = []
    seen_ids = set()
    attempts = 0
    max_attempts = n * 20  # avoid infinite loop on sparse tables

    while len(samples) < n and attempts < max_attempts:
        attempts += 1
        # Pick random rowid range and grab one chunk
        rand_rowid = random.randint(1, max_rowid)
        cur.execute("""
            SELECT chunk_id, text, source_path, text_length
            FROM chunks
            WHERE rowid >= ? AND text IS NOT NULL AND text_length > 50
            LIMIT 1
        """, (rand_rowid,))

        row = cur.fetchone()
        if row is None:
            continue
        if row["chunk_id"] in seen_ids:
            continue

        seen_ids.add(row["chunk_id"])
        tl = row["text_length"]
        if tl < 300:
            cat = "short"
        elif tl < 1000:
            cat = "medium"
        else:
            cat = "long"

        samples.append(ChunkSample(
            chunk_id=row["chunk_id"],
            text=row["text"],
            source_path=row["source_path"] or "",
            text_length=tl,
            category=cat,
        ))

    conn.close()
    random.shuffle(samples)
    return samples[:n]


# ---------------------------------------------------------------------------
# Extraction runner
# ---------------------------------------------------------------------------

def run_extraction(
    client: LLMClient,
    model_name: str,
    text: str,
    chunk_id: str,
) -> ExtractionMetrics:
    """Run extraction and collect metrics. Returns metrics even on failure."""
    metrics = ExtractionMetrics(model_name=model_name, chunk_id=chunk_id)

    prompt = f"Extract all entities and relationships from this text:\n\n{text}"
    start = time.perf_counter()

    try:
        # Try with structured output first (GPT-4o supports it)
        try:
            resp = client.call(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                temperature=0,
                max_tokens=4096,
                response_format=ENTITY_SCHEMA,
            )
        except Exception:
            # Fallback: no structured output (phi4 may not support json_schema)
            resp = client.call(
                prompt=prompt + "\n\nRespond with valid JSON matching this schema: {entities: [...], relationships: [...], table_rows: [...]}",
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                temperature=0,
                max_tokens=4096,
            )

        metrics.latency_ms = (time.perf_counter() - start) * 1000
        metrics.input_tokens = resp.input_tokens
        metrics.output_tokens = resp.output_tokens

        # Parse JSON
        try:
            data = json.loads(resp.text)
            metrics.json_valid = True
        except json.JSONDecodeError:
            # Try to extract JSON from response text
            text_resp = resp.text
            start_idx = text_resp.find("{")
            end_idx = text_resp.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                try:
                    data = json.loads(text_resp[start_idx:end_idx])
                    metrics.json_valid = True
                except json.JSONDecodeError:
                    metrics.json_valid = False
                    metrics.error = "JSON parse failed after extraction"
                    return metrics
            else:
                metrics.json_valid = False
                metrics.error = "No JSON found in response"
                return metrics

        # Count entities
        entities = data.get("entities", [])
        metrics.entity_count = len(entities)
        metrics.relationship_count = len(data.get("relationships", []))
        metrics.table_row_count = len(data.get("table_rows", []))

        # Type distribution
        type_counts = {}
        confidences = []
        for e in entities:
            etype = e.get("entity_type", "UNKNOWN")
            type_counts[etype] = type_counts.get(etype, 0) + 1
            conf = e.get("confidence", 0)
            if isinstance(conf, (int, float)):
                confidences.append(conf)

        metrics.entity_types = type_counts
        metrics.avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    except Exception as e:
        metrics.latency_ms = (time.perf_counter() - start) * 1000
        metrics.error = str(e)

    return metrics


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_extractions(
    samples: list[ChunkSample],
    phi4_metrics: list[ExtractionMetrics],
    gpt4o_metrics: list[ExtractionMetrics],
) -> list[ComparisonResult]:
    """Compare phi4 vs GPT-4o extraction results side-by-side."""
    phi4_by_id = {m.chunk_id: m for m in phi4_metrics}
    gpt4o_by_id = {m.chunk_id: m for m in gpt4o_metrics}

    results = []
    for sample in samples:
        phi4 = phi4_by_id.get(sample.chunk_id)
        gpt4o = gpt4o_by_id.get(sample.chunk_id)

        result = ComparisonResult(
            chunk_id=sample.chunk_id,
            category=sample.category,
            text_preview=sample.text[:200] + "..." if len(sample.text) > 200 else sample.text,
        )

        if phi4:
            result.phi4 = phi4
        if gpt4o:
            result.gpt4o = gpt4o

        if phi4 and gpt4o:
            result.entity_count_delta = phi4.entity_count - gpt4o.entity_count
            result.relationship_count_delta = phi4.relationship_count - gpt4o.relationship_count

        results.append(result)

    return results


def generate_report(results: list[ComparisonResult]) -> dict:
    """Generate summary report from comparison results."""
    total = len(results)
    phi4_success = sum(1 for r in results if r.phi4 and not r.phi4.error)
    gpt4o_success = sum(1 for r in results if r.gpt4o and not r.gpt4o.error)

    phi4_entities = sum(r.phi4.entity_count for r in results if r.phi4 and not r.phi4.error)
    gpt4o_entities = sum(r.gpt4o.entity_count for r in results if r.gpt4o and not r.gpt4o.error)

    phi4_rels = sum(r.phi4.relationship_count for r in results if r.phi4 and not r.phi4.error)
    gpt4o_rels = sum(r.gpt4o.relationship_count for r in results if r.gpt4o and not r.gpt4o.error)

    phi4_json_valid = sum(1 for r in results if r.phi4 and r.phi4.json_valid)
    gpt4o_json_valid = sum(1 for r in results if r.gpt4o and r.gpt4o.json_valid)

    phi4_latencies = [r.phi4.latency_ms for r in results if r.phi4 and not r.phi4.error]
    gpt4o_latencies = [r.gpt4o.latency_ms for r in results if r.gpt4o and not r.gpt4o.error]

    phi4_avg_conf = [r.phi4.avg_confidence for r in results if r.phi4 and not r.phi4.error and r.phi4.avg_confidence > 0]
    gpt4o_avg_conf = [r.gpt4o.avg_confidence for r in results if r.gpt4o and not r.gpt4o.error and r.gpt4o.avg_confidence > 0]

    # Type coverage
    phi4_types = set()
    gpt4o_types = set()
    for r in results:
        if r.phi4 and r.phi4.entity_types:
            phi4_types.update(r.phi4.entity_types.keys())
        if r.gpt4o and r.gpt4o.entity_types:
            gpt4o_types.update(r.gpt4o.entity_types.keys())

    def safe_avg(lst):
        return sum(lst) / len(lst) if lst else 0

    def safe_p50(lst):
        if not lst:
            return 0
        s = sorted(lst)
        return s[len(s) // 2]

    report = {
        "summary": {
            "total_chunks": total,
            "phi4_successes": phi4_success,
            "gpt4o_successes": gpt4o_success,
        },
        "entity_counts": {
            "phi4_total": phi4_entities,
            "gpt4o_total": gpt4o_entities,
            "ratio": round(phi4_entities / max(gpt4o_entities, 1), 2),
        },
        "relationship_counts": {
            "phi4_total": phi4_rels,
            "gpt4o_total": gpt4o_rels,
            "ratio": round(phi4_rels / max(gpt4o_rels, 1), 2),
        },
        "json_compliance": {
            "phi4_valid": phi4_json_valid,
            "gpt4o_valid": gpt4o_json_valid,
            "phi4_rate": round(phi4_json_valid / max(total, 1), 2),
            "gpt4o_rate": round(gpt4o_json_valid / max(total, 1), 2),
        },
        "confidence": {
            "phi4_avg": round(safe_avg(phi4_avg_conf), 3),
            "gpt4o_avg": round(safe_avg(gpt4o_avg_conf), 3),
        },
        "latency_ms": {
            "phi4_avg": round(safe_avg(phi4_latencies)),
            "phi4_p50": round(safe_p50(phi4_latencies)),
            "gpt4o_avg": round(safe_avg(gpt4o_latencies)),
            "gpt4o_p50": round(safe_p50(gpt4o_latencies)),
        },
        "type_coverage": {
            "phi4_types": sorted(phi4_types),
            "gpt4o_types": sorted(gpt4o_types),
            "phi4_only": sorted(phi4_types - gpt4o_types),
            "gpt4o_only": sorted(gpt4o_types - phi4_types),
        },
        "cost_estimate": {
            "phi4_cost_per_chunk": "$0 (local)",
            "gpt4o_total_input_tokens": sum(r.gpt4o.input_tokens for r in results if r.gpt4o and not r.gpt4o.error),
            "gpt4o_total_output_tokens": sum(r.gpt4o.output_tokens for r in results if r.gpt4o and not r.gpt4o.error),
        },
        "decision": "PENDING — review metrics above",
    }

    # Auto-decision logic
    entity_ratio = report["entity_counts"]["ratio"]
    json_rate = report["json_compliance"]["phi4_rate"]
    conf_delta = abs(report["confidence"]["phi4_avg"] - report["confidence"]["gpt4o_avg"])

    if json_rate >= 0.9 and entity_ratio >= 0.7 and conf_delta < 0.15:
        report["decision"] = "APPROVED — phi4 meets quality threshold for production extraction"
    elif json_rate < 0.7:
        report["decision"] = "REJECTED — phi4 JSON compliance too low for structured extraction"
    elif entity_ratio < 0.5:
        report["decision"] = "REJECTED — phi4 finds <50% of GPT-4o entities"
    else:
        report["decision"] = "MARGINAL — review per-chunk results before committing"

    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Parse command-line inputs and run the main ab extraction test workflow."""
    parser = argparse.ArgumentParser(
        description="Clone1 A/B extraction quality test: phi4 vs GPT-4o (not the V2 LanceStore tiered_extract path)"
    )
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--clone1-db", default=DEFAULT_CLONE1_DB, help="Path to Clone1 SQLite index")
    parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE, help="Number of chunks to sample")
    parser.add_argument("--phi4-only", action="store_true", help="Run phi4 only (no GPT-4o for cost savings)")
    parser.add_argument("--gpt4o-only", action="store_true", help="Run GPT-4o only")
    parser.add_argument("--report-only", type=str, help="Generate report from existing results JSON")
    parser.add_argument("--output", default="results/ab_test_latest.json", help="Output results file")
    args = parser.parse_args()

    # Report-only mode
    if args.report_only:
        with open(args.report_only) as f:
            data = json.load(f)
        print(json.dumps(data["report"], indent=2))
        return

    config = load_config(args.config)

    # Check Clone1 database exists
    if not Path(args.clone1_db).exists():
        print(f"ERROR: Clone1 database not found at {args.clone1_db}")
        print()
        print("This test is the Clone1 / Ollama-phi4 vs GPT-4o A/B benchmark. It")
        print("reads chunks from a HybridRAG3_Clone1 SQLite index. If you do not")
        print("have Clone1 on this machine, this test cannot run -- it is NOT the")
        print("same pipeline as scripts/tiered_extract.py (V2 LanceStore Tier 1/2).")
        print()
        print("Either point --clone1-db at an existing Clone1 index:")
        print("  python scripts/ab_extraction_test.py --clone1-db C:\\path\\to\\hybridrag.sqlite3")
        print()
        print("Or run the V2 pipelines directly instead:")
        print("  .venv\\Scripts\\python.exe scripts\\tiered_extract.py --tier 1")
        print("  .venv\\Scripts\\python.exe scripts\\tiered_extract.py --tier 2")
        sys.exit(1)

    # Sample chunks
    print(f"Sampling {args.sample_size} diverse chunks from Clone1 index...")
    samples = sample_chunks(args.clone1_db, args.sample_size)
    print(f"  Got {len(samples)} chunks:")
    cat_counts = {}
    for s in samples:
        cat_counts[s.category] = cat_counts.get(s.category, 0) + 1
    for cat, count in sorted(cat_counts.items()):
        print(f"    {cat}: {count}")

    phi4_metrics = []
    gpt4o_metrics = []

    # --- phi4:14b extraction ---
    if not args.gpt4o_only:
        print("\n=== phi4:14b Extraction (Ollama, local, $0) ===")
        phi4_client = LLMClient(
            model="phi4:14b-q4_K_M",
            deployment="phi4:14b-q4_K_M",
            max_tokens=4096,
            temperature=0,
            timeout_seconds=300,
            provider_override="ollama",
        )
        if not phi4_client.available:
            print("ERROR: Ollama not available. Run: ollama serve && ollama pull phi4:14b-q4_K_M")
            sys.exit(1)

        print(f"  Provider: {phi4_client.provider}")
        for i, sample in enumerate(samples):
            print(f"  [{i+1}/{len(samples)}] {sample.category} chunk ({sample.text_length} chars)...", end=" ", flush=True)
            metrics = run_extraction(phi4_client, "phi4:14b-q4_K_M", sample.text, sample.chunk_id)
            phi4_metrics.append(metrics)
            status = f"{metrics.entity_count} entities, {metrics.latency_ms:.0f}ms"
            if metrics.error:
                status = f"ERROR: {metrics.error[:60]}"
            print(status)

    # --- GPT-4o extraction ---
    if not args.phi4_only:
        print("\n=== GPT-4o Extraction (API, $6.25/1M input) ===")
        gpt4o_client = LLMClient(
            model="gpt-4o",
            deployment="gpt-4o",
            max_tokens=4096,
            temperature=0,
            timeout_seconds=180,
        )
        if not gpt4o_client.available:
            print("ERROR: GPT-4o not available. Set OPENAI_API_KEY.")
            if args.phi4_only is False:
                print("  Run with --phi4-only to test phi4 alone.")
            sys.exit(1)

        print(f"  Provider: {gpt4o_client.provider}")
        for i, sample in enumerate(samples):
            print(f"  [{i+1}/{len(samples)}] {sample.category} chunk ({sample.text_length} chars)...", end=" ", flush=True)
            metrics = run_extraction(gpt4o_client, "gpt-4o", sample.text, sample.chunk_id)
            gpt4o_metrics.append(metrics)
            status = f"{metrics.entity_count} entities, {metrics.latency_ms:.0f}ms"
            if metrics.error:
                status = f"ERROR: {metrics.error[:60]}"
            print(status)

    # --- Compare and report ---
    print("\n=== Comparison Report ===")
    results = compare_extractions(samples, phi4_metrics, gpt4o_metrics)
    report = generate_report(results)

    # Print report
    print(json.dumps(report, indent=2))

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sample_size": len(samples),
        "report": report,
        "per_chunk": [
            {
                "chunk_id": r.chunk_id,
                "category": r.category,
                "text_preview": r.text_preview,
                "phi4": asdict(r.phi4) if r.phi4 else None,
                "gpt4o": asdict(r.gpt4o) if r.gpt4o else None,
                "entity_count_delta": r.entity_count_delta,
            }
            for r in results
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, default=str)

    print(f"\nResults saved to {output_path}")
    print(f"\n{'='*60}")
    print(f"DECISION: {report['decision']}")
    print(f"{'='*60}")

    # Cost projection for full corpus
    if gpt4o_metrics:
        total_in = sum(m.input_tokens for m in gpt4o_metrics if not m.error)
        total_out = sum(m.output_tokens for m in gpt4o_metrics if not m.error)
        n_success = sum(1 for m in gpt4o_metrics if not m.error)
        if n_success > 0:
            avg_in = total_in / n_success
            avg_out = total_out / n_success
            # Estimate for 27.6M chunks (but half after skip list = ~14M)
            est_chunks = 14_000_000
            est_in_cost = (avg_in * est_chunks / 1_000_000) * 2.50  # gpt-4o-mini input
            est_out_cost = (avg_out * est_chunks / 1_000_000) * 10.00  # gpt-4o-mini output
            print(f"\nCost projection (gpt-4o-mini at work, {est_chunks:,} chunks):")
            print(f"  Avg tokens/chunk: {avg_in:.0f} in, {avg_out:.0f} out")
            print(f"  Estimated cost: ${est_in_cost + est_out_cost:,.0f}")
            print(f"  phi4 cost: $0 (local Ollama)")


if __name__ == "__main__":
    main()
