"""
Retrieval Baseline Probe — reviewer — 2026-04-11

Tests 25 real production queries against the 10.4M chunk LanceDB store.
Measures vector search, FTS search, and hybrid search quality + latency.
Outputs results to docs/RETRIEVAL_BASELINE_PROBE_2026-04-11.md

Does NOT require LLM credentials. Tests embedder + store only.
"""

import json
import os
import sys
import time
from pathlib import Path

# NOTE: Do NOT set CUDA_VISIBLE_DEVICES at process level — it masks GPUs
# from torch. The V2 embedder reads this env var to pick gpu_index for
# device="cuda:N", so we set it AFTER torch has seen both GPUs.
# This makes embedder use cuda:1 while keeping both GPUs visible.

v2_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(v2_root))

# Ensure torch sees all GPUs before we hint which one to use
import torch  # noqa: E402 — must import before setting env
assert torch.cuda.is_available(), "CUDA not available"
print(f"GPUs visible to torch: {torch.cuda.device_count()}")
os.environ["CUDA_VISIBLE_DEVICES"] = "1"  # Embedder reads this for gpu_index

from src.config.schema import load_config
from src.store.lance_store import LanceStore, ChunkResult
from src.query.embedder import Embedder

# ---------------------------------------------------------------------------
# Queries — drawn from real corpus metadata captures (logistics 15K files)
# ---------------------------------------------------------------------------
QUERIES = [
    # --- Logistics: PO / Shipment ---
    {"id": "L01", "cat": "Logistics", "q": "shipment status for PO 23-00685", "expect": "PO/shipment doc"},
    {"id": "L02", "cat": "Logistics", "q": "purchase order 23-00292 delivery date", "expect": "PO/procurement doc"},
    {"id": "L03", "cat": "Logistics", "q": "packing list for shipment 23-00327", "expect": "shipment/packing doc"},
    {"id": "L04", "cat": "Logistics", "q": "DD250 form for contract delivery", "expect": "DD250/deliverable doc"},
    {"id": "L05", "cat": "Logistics", "q": "procurement status CLIN items on order", "expect": "procurement spreadsheet"},
    # --- Logistics: Parts / Inventory ---
    {"id": "L06", "cat": "Logistics", "q": "part number 1302-126B specifications", "expect": "parts data"},
    {"id": "L07", "cat": "Logistics", "q": "XL2200VARM3U power supply replacement", "expect": "parts/tools doc"},
    {"id": "L08", "cat": "Logistics", "q": "serial number tracking for GFE warehouse property", "expect": "GFE/warehouse doc"},
    {"id": "L09", "cat": "Logistics", "q": "calibration records for test equipment", "expect": "calibration folder doc"},
    {"id": "L10", "cat": "Logistics", "q": "HAZMAT material safety data sheet", "expect": "HAZMAT doc"},
    # --- Engineering: Maintenance / Radar ---
    {"id": "E01", "cat": "Engineering", "q": "radar transmitter maintenance procedure", "expect": "maintenance/engineering doc"},
    {"id": "E02", "cat": "Engineering", "q": "antenna replacement steps for tower site", "expect": "engineering/tower doc"},
    {"id": "E03", "cat": "Engineering", "q": "power supply troubleshooting guide", "expect": "engineering/troubleshooting"},
    {"id": "E04", "cat": "Engineering", "q": "system acceptance test procedure", "expect": "engineering/test doc"},
    {"id": "E05", "cat": "Engineering", "q": "drawing number 55238 assembly instructions", "expect": "drawing/engineering doc"},
    # --- Lookup: Specific facts ---
    {"id": "F01", "cat": "Lookup", "q": "what part number is the KVM switch", "expect": "parts list/BOM"},
    {"id": "F02", "cat": "Lookup", "q": "point of contact for site visits", "expect": "SOP/contact doc"},
    {"id": "F03", "cat": "Lookup", "q": "PowerEdge server model and configuration", "expect": "IT/server doc"},
    {"id": "F04", "cat": "Lookup", "q": "software license inventory list", "expect": "software license doc"},
    {"id": "F05", "cat": "Lookup", "q": "monitoring system bill of materials components", "expect": "BOM doc"},
    # --- Aggregation: Counting / Listing ---
    {"id": "A01", "cat": "Aggregation", "q": "list all purchase orders from 2023", "expect": "multiple PO docs"},
    {"id": "A02", "cat": "Aggregation", "q": "how many unique part numbers in the inventory", "expect": "inventory/parts spreadsheets"},
    {"id": "A03", "cat": "Aggregation", "q": "all shipment dates for Alpena site", "expect": "shipment docs mentioning Alpena"},
    # --- Cybersecurity ---
    {"id": "C01", "cat": "Cybersecurity", "q": "STIG compliance checklist findings", "expect": "STIG/compliance doc"},
    {"id": "C02", "cat": "Cybersecurity", "q": "ACAS vulnerability scan results", "expect": "ACAS/scan doc"},
]


def vector_only_search(table, query_vec, top_k=5):
    """Vector-only search via LanceDB (no FTS)."""
    vec = query_vec.astype("float32").flatten().tolist()
    try:
        results = table.search(vec).limit(top_k).to_list()
    except Exception as e:
        return [], str(e)
    return results, None


def fts_only_search(table, query_text, top_k=5):
    """FTS-only (BM25) search via LanceDB Tantivy index."""
    try:
        results = table.search(query_text, query_type="fts").limit(top_k).to_list()
    except Exception as e:
        return [], str(e)
    return results, None


def hybrid_search(table, query_vec, query_text, top_k=5):
    """Hybrid (vector + FTS with RRF fusion) search."""
    vec = query_vec.astype("float32").flatten().tolist()
    try:
        # LanceDB hybrid: pass vector via .vector(), text via .text()
        results = (
            table.search(query_type="hybrid")
            .vector(vec)
            .text(query_text)
            .limit(top_k)
            .to_list()
        )
    except Exception as e:
        # Fall back to vector-only
        try:
            results = table.search(vec).limit(top_k).to_list()
            return results, f"hybrid failed ({e}), fell back to vector-only"
        except Exception as e2:
            return [], str(e2)
    return results, None


def format_result(r, idx):
    """Format a single search result for the report."""
    source = r.get("source_path", "?")
    # Trim to last 2 path segments for readability
    parts = source.replace("\\", "/").split("/")
    short_src = "/".join(parts[-2:]) if len(parts) >= 2 else source
    text_preview = (r.get("text", "") or "")[:100].replace("\n", " ").strip()
    # Strip non-ASCII to avoid cp1252 encoding errors on Windows console
    text_preview = text_preview.encode("ascii", "replace").decode("ascii")
    short_src = short_src.encode("ascii", "replace").decode("ascii")
    score = r.get("_distance", r.get("_score", r.get("score", 0)))
    return f"  [{idx}] score={score:.4f} | {short_src}\n      {text_preview}..."


def main():
    print("=" * 70)
    print("RETRIEVAL BASELINE PROBE — reviewer — 2026-04-11")
    print(f"GPU: CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES', 'not set')}")
    print("=" * 70)

    config = load_config(str(v2_root / "config" / "config.yaml"))
    lance_path = str(v2_root / config.paths.lance_db)
    print(f"\nOpening store: {lance_path}")
    store = LanceStore(lance_path)
    chunk_count = store.count()
    print(f"Store: {chunk_count:,} chunks")

    if chunk_count == 0:
        print("ERROR: Empty store.")
        sys.exit(1)

    # Get raw table handle for direct search calls
    table = store._table

    # Check indices
    indices = store.list_indices()
    vec_idx = store.has_vector_index()
    vec_stats = store.vector_index_stats()
    print(f"Vector index: {'YES' if vec_idx else 'NO'}")
    if vec_stats:
        print(f"  Indexed rows: {vec_stats.get('num_indexed_rows', '?')}")
        print(f"  Unindexed rows: {vec_stats.get('num_unindexed_rows', '?')}")
        print(f"  Type: {vec_stats.get('index_type', '?')}")

    # Check FTS index
    fts_ok = False
    try:
        test_fts = table.search("test", query_type="fts").limit(1).to_list()
        fts_ok = True
        print("FTS index: YES")
    except Exception as e:
        print(f"FTS index: NO ({e})")

    # Init embedder on GPU 1
    print("\nInitializing embedder on GPU 1...")
    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )
    # Warm up
    _ = embedder.embed_query("warm up query")
    print("Embedder ready.\n")

    # --- Run all queries ---
    results_data = []
    all_vector_latencies = []
    all_fts_latencies = []
    all_hybrid_latencies = []
    all_embed_latencies = []

    for q in QUERIES:
        print(f"\n{'='*60}")
        print(f"[{q['id']}] {q['cat']}: {q['q']}")
        print(f"  Expected: {q['expect']}")
        print("-" * 60)

        # Embed
        t0 = time.perf_counter()
        query_vec = embedder.embed_query(q["q"])
        embed_ms = (time.perf_counter() - t0) * 1000
        all_embed_latencies.append(embed_ms)

        # Vector-only search
        t0 = time.perf_counter()
        vec_results, vec_err = vector_only_search(table, query_vec, top_k=5)
        vec_ms = (time.perf_counter() - t0) * 1000
        all_vector_latencies.append(vec_ms)

        # FTS-only search
        fts_results, fts_err = [], "skipped"
        fts_ms = 0
        if fts_ok:
            t0 = time.perf_counter()
            fts_results, fts_err = fts_only_search(table, q["q"], top_k=5)
            fts_ms = (time.perf_counter() - t0) * 1000
            all_fts_latencies.append(fts_ms)

        # Hybrid search
        t0 = time.perf_counter()
        hyb_results, hyb_err = hybrid_search(table, query_vec, q["q"], top_k=5)
        hyb_ms = (time.perf_counter() - t0) * 1000
        all_hybrid_latencies.append(hyb_ms)

        print(f"  Embed: {embed_ms:.1f}ms | Vector: {vec_ms:.1f}ms | FTS: {fts_ms:.1f}ms | Hybrid: {hyb_ms:.1f}ms")

        print(f"\n  --- Vector (top 5) ---")
        if vec_err:
            print(f"  ERROR: {vec_err}")
        for i, r in enumerate(vec_results, 1):
            print(format_result(r, i))

        if fts_ok:
            print(f"\n  --- FTS (top 5) ---")
            if fts_err:
                print(f"  ERROR: {fts_err}")
            for i, r in enumerate(fts_results, 1):
                print(format_result(r, i))

        print(f"\n  --- Hybrid (top 5) ---")
        if hyb_err:
            print(f"  NOTE: {hyb_err}")
        for i, r in enumerate(hyb_results, 1):
            print(format_result(r, i))

        # Score relevance (basic: does source path contain expected keywords?)
        q_entry = {
            "id": q["id"],
            "cat": q["cat"],
            "query": q["q"],
            "expect": q["expect"],
            "embed_ms": round(embed_ms, 1),
            "vector_ms": round(vec_ms, 1),
            "fts_ms": round(fts_ms, 1),
            "hybrid_ms": round(hyb_ms, 1),
            "vector_count": len(vec_results),
            "fts_count": len(fts_results),
            "hybrid_count": len(hyb_results),
            "vector_top1_src": (vec_results[0].get("source_path", "") if vec_results else ""),
            "fts_top1_src": (fts_results[0].get("source_path", "") if fts_results else ""),
            "hybrid_top1_src": (hyb_results[0].get("source_path", "") if hyb_results else ""),
            "vector_top1_preview": ((vec_results[0].get("text", "") or "")[:150] if vec_results else ""),
            "fts_top1_preview": ((fts_results[0].get("text", "") or "")[:150] if fts_results else ""),
            "hybrid_top1_preview": ((hyb_results[0].get("text", "") or "")[:150] if hyb_results else ""),
            "vector_top1_score": round(vec_results[0].get("_distance", 0), 4) if vec_results else None,
            "fts_top1_score": round(fts_results[0].get("_score", fts_results[0].get("_distance", 0)), 4) if fts_results else None,
            "hybrid_top1_score": round(hyb_results[0].get("_distance", hyb_results[0].get("_score", 0)), 4) if hyb_results else None,
            "vector_err": vec_err,
            "fts_err": fts_err,
            "hybrid_err": hyb_err,
        }
        results_data.append(q_entry)

    store.close()

    # --- Compute summary stats ---
    def percentile(arr, p):
        if not arr:
            return 0
        s = sorted(arr)
        idx = int(len(s) * p / 100)
        return s[min(idx, len(s) - 1)]

    summary = {
        "total_queries": len(QUERIES),
        "chunk_count": chunk_count,
        "vector_index": vec_idx,
        "fts_index": fts_ok,
        "embed_p50_ms": round(percentile(all_embed_latencies, 50), 1),
        "embed_p95_ms": round(percentile(all_embed_latencies, 95), 1),
        "vector_p50_ms": round(percentile(all_vector_latencies, 50), 1),
        "vector_p95_ms": round(percentile(all_vector_latencies, 95), 1),
        "fts_p50_ms": round(percentile(all_fts_latencies, 50), 1) if all_fts_latencies else None,
        "fts_p95_ms": round(percentile(all_fts_latencies, 95), 1) if all_fts_latencies else None,
        "hybrid_p50_ms": round(percentile(all_hybrid_latencies, 50), 1),
        "hybrid_p95_ms": round(percentile(all_hybrid_latencies, 95), 1),
    }

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Queries: {summary['total_queries']}")
    print(f"Store: {summary['chunk_count']:,} chunks")
    print(f"Vector index: {summary['vector_index']} | FTS index: {summary['fts_index']}")
    print(f"Embed latency:  P50={summary['embed_p50_ms']}ms  P95={summary['embed_p95_ms']}ms")
    print(f"Vector latency: P50={summary['vector_p50_ms']}ms  P95={summary['vector_p95_ms']}ms")
    if summary['fts_p50_ms'] is not None:
        print(f"FTS latency:    P50={summary['fts_p50_ms']}ms  P95={summary['fts_p95_ms']}ms")
    print(f"Hybrid latency: P50={summary['hybrid_p50_ms']}ms  P95={summary['hybrid_p95_ms']}ms")

    # --- Write JSON artifact ---
    artifact = {"summary": summary, "queries": results_data}
    json_path = v2_root / "docs" / "retrieval_baseline_probe_2026-04-11.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"\nJSON artifact: {json_path}")

    # --- Write markdown report ---
    md_path = v2_root / "docs" / "RETRIEVAL_BASELINE_PROBE_2026-04-11.md"
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Retrieval Baseline Probe — 2026-04-11\n\n")
        f.write(f"**Agent:** reviewer | **Repo:** HybridRAG_V2 | **Date:** 2026-04-11 MDT\n\n")
        f.write(f"**Purpose:** Pure vector+FTS retrieval baseline BEFORE entity extraction.\n")
        f.write(f"Measures what the 10.4M chunk store can answer with embeddings alone.\n\n")
        f.write("---\n\n")
        f.write("## Store State\n\n")
        f.write(f"- Chunks: **{chunk_count:,}**\n")
        f.write(f"- Vector index: **{'YES' if vec_idx else 'NO'}**\n")
        if vec_stats:
            f.write(f"  - Indexed rows: {vec_stats.get('num_indexed_rows', '?')}\n")
            f.write(f"  - Unindexed rows: {vec_stats.get('num_unindexed_rows', '?')}\n")
            f.write(f"  - Type: {vec_stats.get('index_type', '?')}\n")
        f.write(f"- FTS index: **{'YES' if fts_ok else 'NO'}**\n")
        f.write(f"- GPU: CUDA_VISIBLE_DEVICES=1\n\n")

        f.write("## Latency Summary\n\n")
        f.write("| Stage | P50 (ms) | P95 (ms) |\n")
        f.write("|-------|----------|----------|\n")
        f.write(f"| Embed | {summary['embed_p50_ms']} | {summary['embed_p95_ms']} |\n")
        f.write(f"| Vector search | {summary['vector_p50_ms']} | {summary['vector_p95_ms']} |\n")
        if summary['fts_p50_ms'] is not None:
            f.write(f"| FTS search | {summary['fts_p50_ms']} | {summary['fts_p95_ms']} |\n")
        f.write(f"| Hybrid search | {summary['hybrid_p50_ms']} | {summary['hybrid_p95_ms']} |\n")
        f.write("\n---\n\n")

        f.write("## Per-Query Results\n\n")
        for r in results_data:
            f.write(f"### [{r['id']}] {r['cat']}: {r['query']}\n\n")
            f.write(f"**Expected:** {r['expect']}\n\n")
            f.write(f"| Mode | Latency | Top-1 Score | Top-1 Source | Error |\n")
            f.write(f"|------|---------|-------------|--------------|-------|\n")

            # Vector row
            v_src = r['vector_top1_src'].replace("\\", "/").split("/")
            v_short = "/".join(v_src[-2:]) if len(v_src) >= 2 else r['vector_top1_src']
            f.write(f"| Vector | {r['vector_ms']}ms | {r['vector_top1_score']} | {v_short} | {r['vector_err'] or '-'} |\n")

            # FTS row
            if r['fts_top1_src']:
                f_src = r['fts_top1_src'].replace("\\", "/").split("/")
                f_short = "/".join(f_src[-2:]) if len(f_src) >= 2 else r['fts_top1_src']
            else:
                f_short = "-"
            f.write(f"| FTS | {r['fts_ms']}ms | {r['fts_top1_score']} | {f_short} | {r['fts_err'] or '-'} |\n")

            # Hybrid row
            h_src = r['hybrid_top1_src'].replace("\\", "/").split("/")
            h_short = "/".join(h_src[-2:]) if len(h_src) >= 2 else r['hybrid_top1_src']
            f.write(f"| Hybrid | {r['hybrid_ms']}ms | {r['hybrid_top1_score']} | {h_short} | {r['hybrid_err'] or '-'} |\n")

            f.write(f"\n**Vector top-1 preview:** {r['vector_top1_preview'][:120]}...\n\n")
            if r['fts_top1_preview']:
                f.write(f"**FTS top-1 preview:** {r['fts_top1_preview'][:120]}...\n\n")
            f.write(f"**Hybrid top-1 preview:** {r['hybrid_top1_preview'][:120]}...\n\n")
            f.write("---\n\n")

        f.write("## Observations\n\n")
        f.write("_To be filled after reviewing results._\n\n")
        f.write("---\n\n")
        f.write("Signed: reviewer | HybridRAG_V2 | 2026-04-11 MDT\n")

    print(f"Report: {md_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
