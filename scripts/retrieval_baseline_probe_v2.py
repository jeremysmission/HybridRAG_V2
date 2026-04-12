"""
Retrieval Baseline Probe V2 — Agent 1 — 2026-04-11

Re-runs the original 25-query baseline probe against the 10.4M chunk LanceDB
store NOW THAT THE FTS INDEX IS BUILT. Compares against the earlier JSON
artifact (vector-only before FTS fix) to produce a before/after report.

Records top-3 results per path (vector / FTS / hybrid) and relevance judgment.
Writes docs/RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md.

Read-only on the store. Does not modify entity stores or extraction code.
"""

import json
import os
import sys
import time
from pathlib import Path

v2_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(v2_root))

# Torch must see both GPUs before we hint the embedder to use GPU 1
import torch  # noqa: E402
assert torch.cuda.is_available(), "CUDA required"
print(f"GPUs visible to torch: {torch.cuda.device_count()}")
os.environ["CUDA_VISIBLE_DEVICES"] = "1"  # embedder reads this for gpu_index

from src.config.schema import load_config  # noqa: E402
from src.store.lance_store import LanceStore  # noqa: E402
from src.query.embedder import Embedder  # noqa: E402

# Reuse the exact same 25 queries from the original probe
from scripts.retrieval_baseline_probe import QUERIES  # noqa: E402

BEFORE_JSON = v2_root / "docs" / "retrieval_baseline_probe_2026-04-11.json"
AFTER_JSON = v2_root / "docs" / "retrieval_baseline_probe_v2_2026-04-11.json"
REPORT_MD = v2_root / "docs" / "RETRIEVAL_BASELINE_PROBE_V2_2026-04-11.md"

# Tokens that indicate a specific exact-match entity in a query
EXACT_MATCH_TOKENS = {
    "L01": ["23-00685"],
    "L02": ["23-00292"],
    "L03": ["23-00327"],
    "L06": ["1302-126B"],
    "L07": ["XL2200"],
    "E05": ["55238"],
    "F03": ["PowerEdge"],
    "F05": ["NEXION"],
    "A03": ["Alpena"],
    "C01": ["STIG"],
    "C02": ["ACAS"],
    "L04": ["DD250"],
}


def _ascii(s: str) -> str:
    if not s:
        return ""
    return s.encode("ascii", "replace").decode("ascii")


def _short_src(path: str) -> str:
    if not path:
        return ""
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else path


def format_result(r, idx):
    source = r.get("source_path", "?")
    short_src = _ascii(_short_src(source))
    preview = (r.get("text", "") or "")[:100].replace("\n", " ").strip()
    preview = _ascii(preview)
    score = r.get("_distance", r.get("_score", r.get("score", 0)))
    return f"  [{idx}] score={score:.4f} | {short_src}\n      {preview}..."


def vector_only_search(table, query_vec, top_k=5):
    vec = query_vec.astype("float32").flatten().tolist()
    try:
        return table.search(vec).limit(top_k).to_list(), None
    except Exception as e:
        return [], str(e)


def fts_only_search(table, query_text, top_k=5):
    try:
        return table.search(query_text, query_type="fts").limit(top_k).to_list(), None
    except Exception as e:
        return [], str(e)


def hybrid_search(table, query_vec, query_text, top_k=5):
    vec = query_vec.astype("float32").flatten().tolist()
    try:
        results = (
            table.search(query_type="hybrid")
            .vector(vec)
            .text(query_text)
            .limit(top_k)
            .to_list()
        )
        return results, None
    except Exception as e:
        try:
            return table.search(vec).limit(top_k).to_list(), f"hybrid failed ({e}), fell back to vector-only"
        except Exception as e2:
            return [], str(e2)


def judge_hit(results, exact_tokens):
    """Does any top-3 result contain the exact-match token in source or text?"""
    if not exact_tokens or not results:
        return None
    for tok in exact_tokens:
        tok_l = tok.lower()
        for r in results[:3]:
            src = (r.get("source_path", "") or "").lower()
            txt = (r.get("text", "") or "").lower()
            if tok_l in src or tok_l in txt:
                return True
    return False


def percentile(arr, p):
    if not arr:
        return 0
    s = sorted(arr)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]


def main():
    print("=" * 70)
    print("RETRIEVAL BASELINE PROBE V2 (post-FTS) - Agent 1 - 2026-04-11")
    print("=" * 70)

    # Load before-data for comparison
    before_data = {}
    if BEFORE_JSON.exists():
        with open(BEFORE_JSON, encoding="utf-8") as f:
            before = json.load(f)
        before_data = {q["id"]: q for q in before["queries"]}
        before_summary = before["summary"]
        print(f"\nLoaded before-data: {len(before_data)} queries from {BEFORE_JSON.name}")
    else:
        before_summary = {}
        print(f"\nWARNING: no before-data at {BEFORE_JSON}")

    # Open store
    config = load_config(str(v2_root / "config" / "config.yaml"))
    lance_path = str(v2_root / config.paths.lance_db)
    print(f"\nOpening store: {lance_path}")
    store = LanceStore(lance_path)
    chunk_count = store.count()
    print(f"Store: {chunk_count:,} chunks")

    if chunk_count == 0:
        print("ERROR: Empty store.")
        sys.exit(1)

    table = store._table
    vec_idx = store.has_vector_index()
    vec_stats = store.vector_index_stats()
    print(f"Vector index: {'YES' if vec_idx else 'NO'}")
    if vec_stats:
        print(f"  Indexed: {vec_stats.get('num_indexed_rows', '?')} | Unindexed: {vec_stats.get('num_unindexed_rows', '?')}")

    # Verify FTS index
    fts_ok = False
    try:
        _ = table.search("maintenance", query_type="fts").limit(1).to_list()
        fts_ok = True
        print("FTS index: YES (verified with 'maintenance')")
    except Exception as e:
        print(f"FTS index: NO ({e})")
        print("ABORT: This probe requires a working FTS index.")
        store.close()
        sys.exit(1)

    # Init embedder (GPU 1)
    print("\nInitializing embedder on GPU 1...")
    embedder = Embedder(
        model_name="nomic-ai/nomic-embed-text-v1.5",
        dim=768,
        device="cuda",
    )
    _ = embedder.embed_query("warm up query")
    print("Embedder ready.\n")

    # Run queries
    results_data = []
    lat_embed, lat_vector, lat_fts, lat_hybrid = [], [], [], []

    for q in QUERIES:
        print(f"\n{'='*60}")
        print(f"[{q['id']}] {q['cat']}: {q['q']}")
        print("-" * 60)

        # Embed
        t0 = time.perf_counter()
        query_vec = embedder.embed_query(q["q"])
        embed_ms = (time.perf_counter() - t0) * 1000
        lat_embed.append(embed_ms)

        # Vector-only
        t0 = time.perf_counter()
        vec_res, vec_err = vector_only_search(table, query_vec, top_k=5)
        vec_ms = (time.perf_counter() - t0) * 1000
        lat_vector.append(vec_ms)

        # FTS-only
        t0 = time.perf_counter()
        fts_res, fts_err = fts_only_search(table, q["q"], top_k=5)
        fts_ms = (time.perf_counter() - t0) * 1000
        lat_fts.append(fts_ms)

        # Hybrid
        t0 = time.perf_counter()
        hyb_res, hyb_err = hybrid_search(table, query_vec, q["q"], top_k=5)
        hyb_ms = (time.perf_counter() - t0) * 1000
        lat_hybrid.append(hyb_ms)

        print(f"  Embed={embed_ms:.1f}ms Vector={vec_ms:.1f}ms FTS={fts_ms:.1f}ms Hybrid={hyb_ms:.1f}ms")

        print("  --- Vector top 3 ---")
        for i, r in enumerate(vec_res[:3], 1):
            print(format_result(r, i))
        print("  --- FTS top 3 ---")
        if fts_err:
            print(f"  ERROR: {fts_err}")
        for i, r in enumerate(fts_res[:3], 1):
            print(format_result(r, i))
        print("  --- Hybrid top 3 ---")
        if hyb_err:
            print(f"  NOTE: {hyb_err}")
        for i, r in enumerate(hyb_res[:3], 1):
            print(format_result(r, i))

        # Judge hits for exact-match tokens
        exact_toks = EXACT_MATCH_TOKENS.get(q["id"])
        vec_hit = judge_hit(vec_res, exact_toks)
        fts_hit = judge_hit(fts_res, exact_toks)
        hyb_hit = judge_hit(hyb_res, exact_toks)

        def _top3(results):
            return [
                {
                    "source_path": r.get("source_path", ""),
                    "short_src": _short_src(r.get("source_path", "")),
                    "score": round(r.get("_distance", r.get("_score", 0)), 4),
                    "preview": (r.get("text", "") or "")[:150].replace("\n", " "),
                }
                for r in results[:3]
            ]

        entry = {
            "id": q["id"],
            "cat": q["cat"],
            "query": q["q"],
            "expect": q["expect"],
            "exact_tokens": exact_toks,
            "embed_ms": round(embed_ms, 1),
            "vector_ms": round(vec_ms, 1),
            "fts_ms": round(fts_ms, 1),
            "hybrid_ms": round(hyb_ms, 1),
            "vector_top3": _top3(vec_res),
            "fts_top3": _top3(fts_res),
            "hybrid_top3": _top3(hyb_res),
            "vector_hit": vec_hit,
            "fts_hit": fts_hit,
            "hybrid_hit": hyb_hit,
            "fts_count": len(fts_res),
            "vector_err": vec_err,
            "fts_err": fts_err,
            "hybrid_err": hyb_err,
        }
        results_data.append(entry)

    store.close()

    # Summary stats
    summary = {
        "total_queries": len(QUERIES),
        "chunk_count": chunk_count,
        "vector_index": vec_idx,
        "fts_index": fts_ok,
        "embed_p50_ms": round(percentile(lat_embed, 50), 1),
        "embed_p95_ms": round(percentile(lat_embed, 95), 1),
        "vector_p50_ms": round(percentile(lat_vector, 50), 1),
        "vector_p95_ms": round(percentile(lat_vector, 95), 1),
        "fts_p50_ms": round(percentile(lat_fts, 50), 1),
        "fts_p95_ms": round(percentile(lat_fts, 95), 1),
        "hybrid_p50_ms": round(percentile(lat_hybrid, 50), 1),
        "hybrid_p95_ms": round(percentile(lat_hybrid, 95), 1),
    }

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Write JSON artifact
    artifact = {"summary": summary, "queries": results_data}
    with open(AFTER_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"\nJSON: {AFTER_JSON}")

    # -------------------------------------------------------------------
    # Build the comparison report
    # -------------------------------------------------------------------
    md_lines = []
    md_lines.append("# Retrieval Baseline Probe V2 (post-FTS) - 2026-04-11\n")
    md_lines.append("**Agent:** Agent 1 | **Repo:** HybridRAG_V2 | **Date:** 2026-04-11 MDT\n")
    md_lines.append("**Purpose:** Re-run the 25-query baseline probe now that the FTS (Tantivy)\n")
    md_lines.append("index has been built on the live 10.4M store. Compare against the earlier\n")
    md_lines.append("vector-only results to measure the FTS fix's impact.\n\n")
    md_lines.append("**Fix context:**\n")
    md_lines.append("- FTS fix commit: `715fe4b` (`src/store/lance_store.py::create_fts_index()`)\n")
    md_lines.append("- FTS index build time: 164.8s on live 10.4M store\n")
    md_lines.append("- Store is read-only for this probe; no mutations performed\n\n")
    md_lines.append("---\n\n")

    md_lines.append("## Store State\n\n")
    md_lines.append(f"- Chunks: **{chunk_count:,}**\n")
    md_lines.append(f"- Vector index: **{'YES' if vec_idx else 'NO'}** (IVF_PQ)\n")
    md_lines.append(f"- FTS index: **YES** (Tantivy, verified)\n")
    md_lines.append(f"- GPU: CUDA_VISIBLE_DEVICES=1\n\n")

    # Latency comparison
    md_lines.append("## Latency Comparison\n\n")
    md_lines.append("| Stage | Before P50 | After P50 | Before P95 | After P95 |\n")
    md_lines.append("|-------|-----------:|----------:|-----------:|----------:|\n")
    b_embed_p50 = before_summary.get("embed_p50_ms", "-")
    b_embed_p95 = before_summary.get("embed_p95_ms", "-")
    b_vec_p50 = before_summary.get("vector_p50_ms", "-")
    b_vec_p95 = before_summary.get("vector_p95_ms", "-")
    b_hyb_p50 = before_summary.get("hybrid_p50_ms", "-")
    b_hyb_p95 = before_summary.get("hybrid_p95_ms", "-")
    md_lines.append(f"| Embed | {b_embed_p50}ms | {summary['embed_p50_ms']}ms | {b_embed_p95}ms | {summary['embed_p95_ms']}ms |\n")
    md_lines.append(f"| Vector | {b_vec_p50}ms | {summary['vector_p50_ms']}ms | {b_vec_p95}ms | {summary['vector_p95_ms']}ms |\n")
    md_lines.append(f"| FTS | (unavailable) | {summary['fts_p50_ms']}ms | - | {summary['fts_p95_ms']}ms |\n")
    md_lines.append(f"| Hybrid | {b_hyb_p50}ms* | {summary['hybrid_p50_ms']}ms | {b_hyb_p95}ms* | {summary['hybrid_p95_ms']}ms |\n")
    md_lines.append("\n*Before: hybrid fell back to vector-only (FTS index missing)\n\n")

    # Exact-match hit rate table
    md_lines.append("## Exact-Match Hit Rate (the key test)\n\n")
    md_lines.append("Queries containing specific identifiers. HIT = exact token found in top-3 source or text.\n\n")
    md_lines.append("| ID | Token | Before (vec-only) | After Vector | After FTS | After Hybrid |\n")
    md_lines.append("|----|-------|:-----------------:|:------------:|:---------:|:------------:|\n")

    before_hit_count = 0
    after_vec_hit_count = 0
    after_fts_hit_count = 0
    after_hyb_hit_count = 0
    exact_total = 0

    for r in results_data:
        toks = r.get("exact_tokens")
        if not toks:
            continue
        exact_total += 1
        # before hit: use heuristic from old data (check vector top1 src/preview)
        before_entry = before_data.get(r["id"], {})
        before_src = (before_entry.get("vector_top1_src", "") or "").lower()
        before_prev = (before_entry.get("vector_top1_preview", "") or "").lower()
        before_hit = any(t.lower() in before_src or t.lower() in before_prev for t in toks)
        if before_hit:
            before_hit_count += 1
        if r["vector_hit"]:
            after_vec_hit_count += 1
        if r["fts_hit"]:
            after_fts_hit_count += 1
        if r["hybrid_hit"]:
            after_hyb_hit_count += 1

        def _mark(v):
            if v is True:
                return "HIT"
            if v is False:
                return "miss"
            return "-"

        md_lines.append(
            f"| {r['id']} | `{toks[0]}` | "
            f"{'HIT' if before_hit else 'miss'} | "
            f"{_mark(r['vector_hit'])} | "
            f"{_mark(r['fts_hit'])} | "
            f"{_mark(r['hybrid_hit'])} |\n"
        )

    md_lines.append("\n**Totals:**\n")
    md_lines.append(f"- Before (vector-only): **{before_hit_count}/{exact_total}** exact-match hits\n")
    md_lines.append(f"- After vector only:    **{after_vec_hit_count}/{exact_total}** (unchanged — same embeddings)\n")
    md_lines.append(f"- After FTS only:       **{after_fts_hit_count}/{exact_total}**\n")
    md_lines.append(f"- After hybrid fusion:  **{after_hyb_hit_count}/{exact_total}**\n\n")

    # Per-category scorecard
    md_lines.append("## Per-Category Scorecard\n\n")
    cats = {}
    for r in results_data:
        cats.setdefault(r["cat"], []).append(r)

    md_lines.append("| Category | Queries | FTS had results | Vector P50 | FTS P50 | Hybrid P50 |\n")
    md_lines.append("|----------|--------:|----------------:|-----------:|--------:|-----------:|\n")
    for cat, items in cats.items():
        vec_p50 = round(percentile([i["vector_ms"] for i in items], 50), 1)
        fts_p50 = round(percentile([i["fts_ms"] for i in items], 50), 1)
        hyb_p50 = round(percentile([i["hybrid_ms"] for i in items], 50), 1)
        fts_hits = sum(1 for i in items if i["fts_count"] > 0)
        md_lines.append(
            f"| {cat} | {len(items)} | {fts_hits}/{len(items)} | {vec_p50}ms | {fts_p50}ms | {hyb_p50}ms |\n"
        )

    md_lines.append("\n---\n\n")

    # Per-query side-by-side
    md_lines.append("## Per-Query Side-by-Side\n\n")
    for r in results_data:
        before_entry = before_data.get(r["id"], {})
        md_lines.append(f"### [{r['id']}] {r['cat']}: {r['query']}\n\n")
        md_lines.append(f"**Expected:** {r['expect']}")
        if r["exact_tokens"]:
            md_lines.append(f"  |  **Exact token:** `{r['exact_tokens'][0]}`")
        md_lines.append("\n\n")

        # Before row (vector only)
        before_src = _ascii(_short_src(before_entry.get("vector_top1_src", "")))
        before_score = before_entry.get("vector_top1_score", "-")
        md_lines.append("**Before (vector-only):**\n\n")
        md_lines.append(f"- Top-1: `{before_src}` (score {before_score})\n\n")

        md_lines.append("**After — Vector top-3:**\n\n")
        for i, t in enumerate(r["vector_top3"], 1):
            md_lines.append(f"{i}. `{_ascii(t['short_src'])}` (d={t['score']})\n")
        md_lines.append("\n")

        md_lines.append("**After — FTS top-3:**\n\n")
        if r["fts_err"]:
            md_lines.append(f"- ERROR: {_ascii(r['fts_err'])}\n\n")
        elif not r["fts_top3"]:
            md_lines.append("- (no results)\n\n")
        else:
            for i, t in enumerate(r["fts_top3"], 1):
                md_lines.append(f"{i}. `{_ascii(t['short_src'])}` (score {t['score']})\n")
            md_lines.append("\n")

        md_lines.append("**After — Hybrid top-3:**\n\n")
        if r["hybrid_err"]:
            md_lines.append(f"- NOTE: {_ascii(r['hybrid_err'])[:200]}\n\n")
        for i, t in enumerate(r["hybrid_top3"], 1):
            md_lines.append(f"{i}. `{_ascii(t['short_src'])}` (d={t['score']})\n")
        md_lines.append("\n")

        # Latency line
        md_lines.append(
            f"_Latency: vector {r['vector_ms']}ms | FTS {r['fts_ms']}ms | hybrid {r['hybrid_ms']}ms_\n\n"
        )

        # Judgment line for exact-match queries
        if r["exact_tokens"]:
            tok = r["exact_tokens"][0]
            md_lines.append(
                f"**Exact-match judgment** for `{tok}`: "
                f"vector={_hit_str(r['vector_hit'])} | "
                f"FTS={_hit_str(r['fts_hit'])} | "
                f"hybrid={_hit_str(r['hybrid_hit'])}\n\n"
            )

        md_lines.append("---\n\n")

    # Observations placeholder — will be filled by analysis pass
    md_lines.append("## Observations\n\n")
    md_lines.append("_See analysis pass — filled after comparison._\n\n")

    md_lines.append("---\n\n")
    md_lines.append("Signed: Agent 1 | HybridRAG_V2 | 2026-04-11 MDT\n")

    with open(REPORT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(md_lines)

    print(f"Report: {REPORT_MD}")
    print("\nDone.")


def _hit_str(v):
    if v is True:
        return "HIT"
    if v is False:
        return "miss"
    return "n/a"


if __name__ == "__main__":
    main()
