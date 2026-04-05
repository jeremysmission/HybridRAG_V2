"""
Demo rehearsal script — runs the 10 demo queries and verifies results.

Usage:
    python scripts/demo_rehearsal.py               # full rehearsal
    python scripts/demo_rehearsal.py --dry-run      # print demo script only
    python scripts/demo_rehearsal.py --timing        # detailed per-stage timing

Exits 0 if all queries pass, 1 if any fail.

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Demo query definitions
# ---------------------------------------------------------------------------

@dataclass
class DemoQuery:
    """A single demo query with expected results and talking points."""

    number: int
    title: str
    query: str
    expected_path: str
    expected_confidence: str
    expected_facts: list[str]
    latency_budget_ms: int
    talking_points: list[str] = field(default_factory=list)
    golden_id: str | None = None
    is_refusal: bool = False
    is_crag: bool = False
    is_comparison: bool = False


DEMO_QUERIES: list[DemoQuery] = [
    DemoQuery(
        number=1,
        title="Slam Dunk (SEMANTIC)",
        query="What is the transmitter output power at Riverside Observatory?",
        expected_path="SEMANTIC",
        expected_confidence="HIGH",
        expected_facts=["1.2 kW"],
        latency_budget_ms=5000,
        talking_points=[
            "Bread and butter factual query — instant answer with citation.",
            "No need to open the PDF and ctrl-F through it.",
        ],
        golden_id="GQ-008",
    ),
    DemoQuery(
        number=2,
        title="Entity Lookup (ENTITY)",
        query="Who is the field technician for the Riverside radar site?",
        expected_path="ENTITY",
        expected_confidence="HIGH",
        expected_facts=["Mike Torres"],
        latency_budget_ms=5000,
        talking_points=[
            "Path badge says ENTITY — queried the entity store directly.",
            "Faster and more precise than full-text search.",
        ],
        golden_id="GQ-007",
    ),
    DemoQuery(
        number=3,
        title="Aggregation (AGGREGATE)",
        query="List all parts replaced at Riverside Observatory during the March 2024 visit.",
        expected_path="AGGREGATE",
        expected_confidence="HIGH",
        expected_facts=["WR-4471", "RF Connector", "SN-2901", "SN-2902"],
        latency_budget_ms=5000,
        talking_points=[
            "Aggregation was impossible in V1 — V2 counts across documents.",
            "Matters when a PM asks 'how many parts did we use this quarter.'",
        ],
        golden_id="GQ-015",
    ),
    DemoQuery(
        number=4,
        title="Tabular Data (TABULAR)",
        query="What is the status of PO-2024-0501?",
        expected_path="TABULAR",
        expected_confidence="HIGH",
        expected_facts=["IN TRANSIT", "FM-220", "Cedar Ridge"],
        latency_budget_ms=5000,
        talking_points=[
            "Came from a spreadsheet, not a narrative document.",
            "System extracted table rows during ingestion — queryable like a DB.",
        ],
        golden_id="GQ-011",
    ),
    DemoQuery(
        number=5,
        title="Complex / Multi-hop (COMPLEX)",
        query="Compare the maintenance issues at Riverside Observatory versus Cedar Ridge.",
        expected_path="COMPLEX",
        expected_confidence="PARTIAL",
        expected_facts=["SN-2847", "noise floor", "CH3", "filter module", "corrosion"],
        latency_budget_ms=15000,
        talking_points=[
            "Required information from two separate documents.",
            "Decomposed into sub-queries, retrieved from both, merged results.",
            "PARTIAL confidence is correct — comparisons always have gaps.",
        ],
        golden_id="GQ-019",
    ),
    DemoQuery(
        number=6,
        title="Messy Input Handling (SEMANTIC on tier2)",
        query="What workaround was applied for the CH3 noise issue?",
        expected_path="SEMANTIC",
        expected_confidence="HIGH",
        expected_facts=["attenuation", "2 steps", "+6dB", "integration time", "4 to 8 sweeps"],
        latency_budget_ms=5000,
        talking_points=[
            "Answer buried three levels deep in a RE:RE:RE email chain.",
            "Mixed with unrelated endpoint protection content.",
            "This is the tribal knowledge that gets lost when someone PCSes.",
        ],
        golden_id="GQ-018",
    ),
    DemoQuery(
        number=7,
        title="Deliberate Refusal (NOT_FOUND)",
        query="What maintenance was performed at Fort Wainwright in 2024?",
        expected_path="SEMANTIC",
        expected_confidence="NOT_FOUND",
        expected_facts=[],
        latency_budget_ms=5000,
        talking_points=[
            "THE TRUST-BUILDING MOMENT.",
            "The system knows what it does NOT know.",
            "Fort Wainwright is not in our corpus — it says so instead of guessing.",
            "That refusal IS the feature.",
        ],
        golden_id="GQ-025",
        is_refusal=True,
    ),
    DemoQuery(
        number=8,
        title="CRAG Verification",
        query="What was the general condition of the equipment during recent visits?",
        expected_path="SEMANTIC",
        expected_confidence="PARTIAL",
        expected_facts=["maintenance", "repair"],
        latency_budget_ms=20000,
        talking_points=[
            "System caught itself giving a weak answer — went back for more context.",
            "Corrective RAG: self-correcting retrieval.",
            "Does not ship an answer it is not confident in without trying harder.",
        ],
        golden_id="GQ-022",
        is_crag=True,
    ),
    DemoQuery(
        number=9,
        title="V1 vs V2 Side-by-Side",
        query="What parts are currently backordered?",
        expected_path="TABULAR",
        expected_confidence="HIGH",
        expected_facts=["PS-800", "Granite Peak"],
        latency_budget_ms=5000,
        talking_points=[
            "V1 could not read structured data — spreadsheets were invisible.",
            "V2 extracted table rows during ingestion — answers in < 3 seconds.",
            "Same question, same corpus, fundamentally different architecture.",
        ],
        golden_id="GQ-014",
        is_comparison=True,
    ),
    DemoQuery(
        number=10,
        title="Audience Choice",
        query="When is the next scheduled maintenance at Thule Air Base?",
        expected_path="ENTITY",
        expected_confidence="HIGH",
        expected_facts=["2025-06-15"],
        latency_budget_ms=5000,
        talking_points=[
            "Backup query if audience is quiet.",
            "In the live demo, let the audience ask anything.",
        ],
        golden_id="GQ-010",
    ),
]


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Result of running one demo query."""

    query: DemoQuery
    passed: bool = False
    answer: str = ""
    actual_confidence: str = ""
    actual_path: str = ""
    latency_ms: int = 0
    facts_found: list[str] = field(default_factory=list)
    facts_missing: list[str] = field(default_factory=list)
    confidence_ok: bool = False
    path_ok: bool = False
    latency_ok: bool = False
    error: str | None = None
    stage_times: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Dry-run printer
# ---------------------------------------------------------------------------

def print_dry_run() -> None:
    """Print the demo script without running any queries."""
    print("=" * 72)
    print("  HybridRAG V2 — Demo Rehearsal Script (DRY RUN)")
    print("  10 queries in progression")
    print("=" * 72)
    print()

    for dq in DEMO_QUERIES:
        print(f"--- Query {dq.number}: {dq.title} ---")
        print(f"  Ask:        {dq.query}")
        print(f"  Path:       {dq.expected_path}")
        print(f"  Confidence: {dq.expected_confidence}")
        print(f"  Key facts:  {', '.join(dq.expected_facts) if dq.expected_facts else '(none — refusal)'}")
        print(f"  Budget:     {dq.latency_budget_ms} ms")
        if dq.talking_points:
            print("  Talking points:")
            for tp in dq.talking_points:
                print(f"    - {tp}")
        print()

    print("=" * 72)
    print("  End of dry-run script.")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Query runner
# ---------------------------------------------------------------------------

def run_query(dq: DemoQuery, pipeline, show_timing: bool = False) -> QueryResult:
    """Run a single demo query through the pipeline and evaluate."""
    result = QueryResult(query=dq)

    try:
        t0 = time.perf_counter()
        response = pipeline.query(dq.query)
        total_ms = int((time.perf_counter() - t0) * 1000)

        result.answer = response.answer
        result.actual_confidence = response.confidence
        result.actual_path = response.query_path
        result.latency_ms = total_ms

        if show_timing:
            result.stage_times["total"] = total_ms
            result.stage_times["pipeline_reported"] = response.latency_ms

        # Check facts
        answer_upper = response.answer.upper()
        for fact in dq.expected_facts:
            if fact.upper() in answer_upper:
                result.facts_found.append(fact)
            else:
                result.facts_missing.append(fact)

        # For refusal queries, check that answer contains NOT_FOUND
        if dq.is_refusal:
            facts_ok = "NOT_FOUND" in response.answer.upper()
        else:
            facts_ok = len(result.facts_missing) == 0

        # Check confidence
        result.confidence_ok = response.confidence == dq.expected_confidence

        # Check path (allow SEMANTIC fallback for structured types)
        result.path_ok = response.query_path == dq.expected_path

        # Check latency
        result.latency_ok = total_ms <= dq.latency_budget_ms

        result.passed = facts_ok and result.confidence_ok

    except Exception as exc:
        result.error = str(exc)
        result.passed = False

    return result


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

_CONF_SYMBOLS = {"HIGH": "[HIGH]", "PARTIAL": "[PART]", "NOT_FOUND": "[NONE]", "UNKNOWN": "[????]"}


def print_report(results: list[QueryResult], show_timing: bool = False) -> int:
    """Print formatted rehearsal report. Returns exit code."""
    print()
    print("=" * 72)
    print("  HybridRAG V2 — Demo Rehearsal Report")
    print("=" * 72)
    print()

    pass_count = 0
    fail_count = 0

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        icon = "  OK" if r.passed else "FAIL"

        if r.passed:
            pass_count += 1
        else:
            fail_count += 1

        print(f"[{icon}] Q{r.query.number}: {r.query.title}")
        print(f"       Query:      {r.query.query}")

        if r.error:
            print(f"       ERROR:      {r.error}")
            print()
            continue

        print(f"       Answer:     {r.answer[:120]}{'...' if len(r.answer) > 120 else ''}")
        print(f"       Confidence: {r.actual_confidence} (expected {r.query.expected_confidence}) {'OK' if r.confidence_ok else 'MISMATCH'}")
        print(f"       Path:       {r.actual_path} (expected {r.query.expected_path}) {'OK' if r.path_ok else 'MISMATCH'}")
        print(f"       Latency:    {r.latency_ms} ms (budget {r.query.latency_budget_ms} ms) {'OK' if r.latency_ok else 'OVER'}")

        if r.facts_found:
            print(f"       Facts OK:   {', '.join(r.facts_found)}")
        if r.facts_missing:
            print(f"       Facts MISS: {', '.join(r.facts_missing)}")

        if show_timing and r.stage_times:
            print("       Timing:")
            for stage, ms in r.stage_times.items():
                print(f"         {stage}: {ms} ms")

        print()

    # Summary
    print("-" * 72)
    print(f"  Results: {pass_count} passed, {fail_count} failed, {len(results)} total")
    print()

    if fail_count == 0:
        print("  REHEARSAL PASSED — all demo queries verified.")
    else:
        print("  REHEARSAL FAILED — fix failing queries before demo.")

    print("-" * 72)
    print()

    return 0 if fail_count == 0 else 1


# ---------------------------------------------------------------------------
# Pipeline loader
# ---------------------------------------------------------------------------

def load_pipeline():
    """
    Load the HybridRAG V2 query pipeline.

    Imports from the project source. Raises ImportError if dependencies
    are missing or the system is not configured.
    """
    # Add project root to path
    import os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.config.schema import load_config
    from scripts.boot import boot_system

    config = load_config()
    system = boot_system(config)
    return system.pipeline


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="HybridRAG V2 demo rehearsal — run and verify 10 demo queries."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the demo script without running queries.",
    )
    parser.add_argument(
        "--timing",
        action="store_true",
        help="Show detailed per-stage timing breakdown.",
    )
    args = parser.parse_args()

    if args.dry_run:
        print_dry_run()
        return 0

    # Load pipeline
    print("Loading HybridRAG V2 pipeline...")
    try:
        pipeline = load_pipeline()
    except Exception as exc:
        print(f"ERROR: Could not load pipeline: {exc}", file=sys.stderr)
        print("Hint: Run 'python scripts/boot.py' first to verify system health.", file=sys.stderr)
        return 1

    print(f"Pipeline ready. Running {len(DEMO_QUERIES)} demo queries...\n")

    # Run all queries
    results: list[QueryResult] = []
    for dq in DEMO_QUERIES:
        print(f"  Running Q{dq.number}: {dq.title}...", end=" ", flush=True)
        result = run_query(dq, pipeline, show_timing=args.timing)
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} ({result.latency_ms} ms)")
        results.append(result)

    # Print full report
    return print_report(results, show_timing=args.timing)


if __name__ == "__main__":
    sys.exit(main())
