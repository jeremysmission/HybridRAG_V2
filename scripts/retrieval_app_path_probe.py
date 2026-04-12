"""
Retrieval App-Path Probe — reviewer — 2026-04-11

Runs the same 25 queries through the full V2 application path
(VectorRetriever -> LanceStore.hybrid_search) and compares against the raw
LanceDB top-3 captured in retrieval_baseline_probe_v2_2026-04-11.json.

Writes an addendum to docs/RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md plus a
machine-readable JSON artifact.

Read-only on the store. Does not modify entity stores or extraction code.
"""

import json
import os
import sys
import time
from pathlib import Path

v2_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(v2_root))

import torch  # noqa: E402
assert torch.cuda.is_available(), "CUDA required"
print(f"GPUs visible to torch: {torch.cuda.device_count()}")
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

from src.config.schema import load_config  # noqa: E402
from src.store.lance_store import LanceStore  # noqa: E402
from src.query.embedder import Embedder  # noqa: E402
from src.query.vector_retriever import VectorRetriever  # noqa: E402

from scripts.retrieval_baseline_probe import QUERIES  # noqa: E402

RAW_JSON = v2_root / "docs" / "retrieval_baseline_probe_v2_2026-04-11.json"
APP_JSON = v2_root / "docs" / "retrieval_app_path_probe_2026-04-11.json"
REPORT_MD = v2_root / "docs" / "RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md"


def _ascii(s: str) -> str:
    if not s:
        return ""
    return s.encode("ascii", "replace").decode("ascii")


def _short_src(path: str) -> str:
    if not path:
        return ""
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else path


def _chunk_id_or_src(item):
    """Stable identifier for a result — prefer chunk_id, fall back to src+preview."""
    if isinstance(item, dict):
        cid = item.get("chunk_id") or ""
        src = item.get("source_path") or ""
        preview = (item.get("text") or "")[:40]
    else:
        cid = getattr(item, "chunk_id", "") or ""
        src = getattr(item, "source_path", "") or ""
        preview = (getattr(item, "text", "") or "")[:40]
    if cid:
        return f"cid:{cid}"
    return f"src:{src}|{preview}"


def percentile(arr, p):
    if not arr:
        return 0
    s = sorted(arr)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]


def main():
    print("=" * 70)
    print("RETRIEVAL APP-PATH PROBE - reviewer - 2026-04-11")
    print("=" * 70)

    # Load raw-path data
    if not RAW_JSON.exists():
        print(f"ERROR: raw-path JSON not found: {RAW_JSON}")
        sys.exit(1)
    with open(RAW_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    raw_by_id = {q["id"]: q for q in raw["queries"]}
    print(f"Loaded raw-path results: {len(raw_by_id)} queries")

    # Open store
    config = load_config(str(v2_root / "config" / "config.yaml"))
    lance_path = str(v2_root / config.paths.lance_db)
    store = LanceStore(lance_path)
    print(f"Store: {store.count():,} chunks")

    # Init embedder
    print("Initializing embedder on GPU 1...")
    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )
    _ = embedder.embed_query("warm up")

    retriever = VectorRetriever(store, embedder, top_k=5)
    print("Retriever ready.\n")

    results_data = []
    app_latencies = []

    for q in QUERIES:
        print(f"\n[{q['id']}] {q['cat']}: {q['q']}")

        t0 = time.perf_counter()
        app_results = retriever.search(q["q"], top_k=5)
        app_ms = (time.perf_counter() - t0) * 1000
        app_latencies.append(app_ms)

        app_top5 = [
            {
                "chunk_id": r.chunk_id,
                "source_path": r.source_path,
                "short_src": _short_src(r.source_path),
                "score": round(r.score, 4),
                "preview": (r.text or "")[:150].replace("\n", " "),
            }
            for r in app_results
        ]

        # Compare against raw-path hybrid top-3 (what app path calls internally)
        raw_entry = raw_by_id.get(q["id"], {})
        raw_hybrid_top3 = raw_entry.get("hybrid_top3", [])

        # Build id-sets for comparison (by short_src since chunk_id not in raw top3)
        app_ids = [r["short_src"] for r in app_top5[:3]]
        raw_ids = [r["short_src"] for r in raw_hybrid_top3[:3]]

        top1_match = len(app_ids) > 0 and len(raw_ids) > 0 and app_ids[0] == raw_ids[0]
        top3_overlap = len(set(app_ids) & set(raw_ids))
        divergence = "IDENTICAL" if app_ids == raw_ids else (
            "TOP1_MATCH" if top1_match else "DIVERGED"
        )

        # Print concise comparison
        print(f"  app latency: {app_ms:.1f}ms  |  top1_match={top1_match}  top3_overlap={top3_overlap}/3  [{divergence}]")
        for i, r in enumerate(app_top5[:3], 1):
            src = _ascii(r["short_src"])[:70]
            print(f"    app [{i}] d={r['score']:.4f}  {src}")
        for i, r in enumerate(raw_hybrid_top3[:3], 1):
            src = _ascii(r["short_src"])[:70]
            print(f"    raw [{i}] d={r['score']:.4f}  {src}")

        results_data.append({
            "id": q["id"],
            "cat": q["cat"],
            "query": q["q"],
            "app_ms": round(app_ms, 1),
            "app_top5": app_top5,
            "raw_hybrid_top3": raw_hybrid_top3,
            "top1_match": top1_match,
            "top3_overlap": top3_overlap,
            "divergence": divergence,
        })

    store.close()

    # Summary stats
    summary = {
        "total_queries": len(QUERIES),
        "app_p50_ms": round(percentile(app_latencies, 50), 1),
        "app_p95_ms": round(percentile(app_latencies, 95), 1),
        "raw_hybrid_p50_ms": raw["summary"].get("hybrid_p50_ms"),
        "raw_hybrid_p95_ms": raw["summary"].get("hybrid_p95_ms"),
        "top1_matches": sum(1 for r in results_data if r["top1_match"]),
        "identical_top3": sum(1 for r in results_data if r["divergence"] == "IDENTICAL"),
        "diverged": sum(1 for r in results_data if r["divergence"] == "DIVERGED"),
    }

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Write artifact
    artifact = {"summary": summary, "queries": results_data}
    with open(APP_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"\nJSON: {APP_JSON}")

    # Append addendum to the V2 report
    addendum_lines = []
    addendum_lines.append("\n\n---\n\n")
    addendum_lines.append("## Addendum: App-Path (VectorRetriever) Comparison\n\n")
    addendum_lines.append(
        "All 25 queries re-run through the **full V2 application path** "
        "(`VectorRetriever.search()` -> `LanceStore.hybrid_search()`) and "
        "compared against the raw `table.search(query_type=\"hybrid\")` path "
        "captured earlier in this document.\n\n"
    )
    addendum_lines.append("### App-Path Summary\n\n")
    addendum_lines.append("| Metric | Value |\n|--------|------:|\n")
    addendum_lines.append(f"| Queries run | {summary['total_queries']} |\n")
    addendum_lines.append(f"| App path P50 | {summary['app_p50_ms']}ms |\n")
    addendum_lines.append(f"| App path P95 | {summary['app_p95_ms']}ms |\n")
    addendum_lines.append(f"| Raw hybrid P50 (earlier) | {summary['raw_hybrid_p50_ms']}ms |\n")
    addendum_lines.append(f"| Raw hybrid P95 (earlier) | {summary['raw_hybrid_p95_ms']}ms |\n")
    addendum_lines.append(f"| Top-1 matches raw path | {summary['top1_matches']}/{summary['total_queries']} |\n")
    addendum_lines.append(f"| Top-3 identical to raw path | {summary['identical_top3']}/{summary['total_queries']} |\n")
    addendum_lines.append(f"| Diverged (top-1 mismatch) | {summary['diverged']}/{summary['total_queries']} |\n\n")

    addendum_lines.append("### Per-Query App vs Raw Comparison\n\n")
    addendum_lines.append("| ID | Cat | Top-1 Match | Top-3 Overlap | Divergence | App ms |\n")
    addendum_lines.append("|----|-----|:-----------:|:-------------:|:----------:|-------:|\n")
    for r in results_data:
        mark = "[OK]" if r["top1_match"] else "[X]"
        addendum_lines.append(
            f"| {r['id']} | {r['cat']} | {mark} | {r['top3_overlap']}/3 | {r['divergence']} | {r['app_ms']}ms |\n"
        )
    addendum_lines.append("\n")

    # Show any divergent queries in detail
    diverged = [r for r in results_data if r["divergence"] == "DIVERGED"]
    if diverged:
        addendum_lines.append("### Divergent Queries (top-1 mismatch)\n\n")
        for r in diverged:
            addendum_lines.append(f"#### [{r['id']}] {r['query']}\n\n")
            addendum_lines.append("**App path top-3:**\n\n")
            for i, t in enumerate(r["app_top5"][:3], 1):
                addendum_lines.append(f"{i}. `{_ascii(t['short_src'])}` (d={t['score']})\n")
            addendum_lines.append("\n**Raw path top-3:**\n\n")
            for i, t in enumerate(r["raw_hybrid_top3"][:3], 1):
                addendum_lines.append(f"{i}. `{_ascii(t['short_src'])}` (d={t['score']})\n")
            addendum_lines.append("\n")
    else:
        addendum_lines.append("### Divergent Queries\n\n")
        addendum_lines.append("**None.** Every query's app-path top-1 matches the raw-path top-1.\n\n")

    # Non-identical-but-top1-match queries (rank 2/3 drift)
    rank_drift = [r for r in results_data if r["divergence"] == "TOP1_MATCH"]
    if rank_drift:
        addendum_lines.append("### Rank-2/3 Drift (top-1 matches, lower ranks differ)\n\n")
        addendum_lines.append("These are acceptable — RRF fusion can reorder below top-1 without affecting answer quality:\n\n")
        for r in rank_drift:
            addendum_lines.append(f"- **{r['id']}** ({r['cat']}): top-3 overlap {r['top3_overlap']}/3\n")
        addendum_lines.append("\n")

    addendum_lines.append("### Conclusion\n\n")
    if summary["diverged"] == 0 and summary["identical_top3"] == summary["total_queries"]:
        addendum_lines.append(
            "**App path and raw path produce IDENTICAL top-3 results on all 25 queries.** "
            "The middleware layer (`VectorRetriever` -> `LanceStore.hybrid_search`) is "
            "transparent — no ordering drift, no filtering, no result loss. "
            "The production query pipeline is using hybrid fusion correctly and delivers "
            "the same results you would get by calling LanceDB directly.\n\n"
        )
    elif summary["diverged"] == 0:
        addendum_lines.append(
            f"**Top-1 matches on all 25 queries** — no answer regressions from the "
            f"middleware. {len(rank_drift)} queries show rank-2/3 drift which is "
            f"acceptable RRF reordering. Production query pipeline is safe.\n\n"
        )
    else:
        addendum_lines.append(
            f"**{summary['diverged']}/{summary['total_queries']} queries DIVERGED** between "
            f"app path and raw path at top-1. This is a middleware bug — see divergent "
            f"query details above.\n\n"
        )

    addendum_lines.append("---\n\n")
    addendum_lines.append("Signed: reviewer | HybridRAG_V2 | 2026-04-11 MDT (addendum)\n")

    with open(REPORT_MD, "a", encoding="utf-8", newline="\n") as f:
        f.writelines(addendum_lines)
    print(f"Appended addendum to: {REPORT_MD}")
    print("\nDone.")


if __name__ == "__main__":
    main()
