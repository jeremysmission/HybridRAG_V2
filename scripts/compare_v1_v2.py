"""
V1 vs V2 comparison harness for HybridRAG golden queries.

Usage:
    python scripts/compare_v1_v2.py
    python scripts/compare_v1_v2.py --v1 http://localhost:8000 --v2 http://localhost:8001
    python scripts/compare_v1_v2.py --judge
    python scripts/compare_v1_v2.py --v1-results tests/golden_eval/results/v1_captured.json
    python scripts/compare_v1_v2.py --report docs/V1_vs_V2_Comparison.md
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
import httpx

V2_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = V2_ROOT / "tests" / "golden_eval" / "golden_queries.json"
RESULTS_DIR = V2_ROOT / "tests" / "golden_eval" / "results"
logger = logging.getLogger("compare_v1_v2")
TIMEOUT = 30.0


def _check_facts(expected: list[str], text: str) -> tuple[list[str], list[str]]:
    lower = text.lower()
    found = [f for f in expected if f.lower() in lower]
    missing = [f for f in expected if f.lower() not in lower]
    return found, missing


def _fact_coverage(expected: list[str], text: str) -> float:
    if not expected:
        return 1.0
    found, _ = _check_facts(expected, text)
    return len(found) / len(expected)


def _query_api(client: httpx.Client, base_url: str, payload: dict,
               extra_fields: dict) -> dict:
    """POST to /query, return normalised result. extra_fields are defaults for the tag."""
    start = time.perf_counter()
    unavail = {"status": "UNAVAILABLE", "answer": "", "chunks_used": 0, "sources": [],
               **extra_fields}
    try:
        resp = client.post(f"{base_url.rstrip('/')}/query", json=payload, timeout=TIMEOUT)
        latency_ms = int((time.perf_counter() - start) * 1000)
        unavail["latency_ms"] = latency_ms
        if resp.status_code >= 500:
            return unavail
        data = resp.json()
        result = {"status": "OK", "answer": data.get("answer", ""),
                  "latency_ms": int(data.get("latency_ms", latency_ms)),
                  "chunks_used": data.get("chunks_used", 0),
                  "sources": data.get("sources", [])}
        for k in extra_fields:
            result[k] = data.get(k, extra_fields[k])
        if data.get("error"):
            result["error"] = data["error"]
        return result
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as exc:
        unavail["latency_ms"] = int((time.perf_counter() - start) * 1000)
        unavail["error"] = str(exc)
        return unavail


def _query_v1(client: httpx.Client, base_url: str, query: str) -> dict:
    return _query_api(client, base_url, {"question": query},
                      {"tokens_in": 0, "tokens_out": 0})


def _query_v2(client: httpx.Client, base_url: str, query: str) -> dict:
    return _query_api(client, base_url, {"query": query},
                      {"confidence": "", "query_path": "", "input_tokens": 0, "output_tokens": 0})


def _judge_pair(query: str, v1_answer: str, v2_answer: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        return {"preference": "SKIP", "reasoning": "No OPENAI_API_KEY set."}
    base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    prompt = (
        "You are an impartial evaluator. Given a question and two answers (A and B), "
        "decide which is better. Respond with ONLY valid JSON:\n"
        '{"preference": "A" | "B" | "TIE", "reasoning": "<1-2 sentences>"}\n\n'
        f"Question: {query}\n\nAnswer A (V1):\n{v1_answer[:2000]}\n\n"
        f"Answer B (V2):\n{v2_answer[:2000]}")
    try:
        with httpx.Client(timeout=60.0) as c:
            resp = c.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "gpt-4o", "temperature": 0,
                      "messages": [{"role": "user", "content": prompt}]})
            result = json.loads(resp.json()["choices"][0]["message"]["content"])
            pref = result.get("preference", "TIE")
            pref = {"A": "V1", "B": "V2"}.get(pref, pref)
            return {"preference": pref, "reasoning": result.get("reasoning", "")}
    except Exception as exc:
        logger.warning("Judge call failed: %s", exc)
        return {"preference": "ERROR", "reasoning": str(exc)}


def _score_query(qdef: dict, v1: dict | None, v2: dict | None) -> dict:
    expected = qdef["expected_facts"]
    rec: dict = {"id": qdef["id"], "query": qdef["query"],
                 "query_type": qdef["query_type"], "expected_facts": expected}
    for tag, res in [("v1", v1), ("v2", v2)]:
        if res is None or res.get("status") == "UNAVAILABLE":
            rec.update({f"{tag}_status": "UNAVAILABLE", f"{tag}_answer": "",
                        f"{tag}_latency_ms": res["latency_ms"] if res else 0,
                        f"{tag}_fact_coverage": 0.0, f"{tag}_facts_found": [],
                        f"{tag}_facts_missing": expected, f"{tag}_chunks_used": 0,
                        f"{tag}_sources": []})
            continue
        found, missing = _check_facts(expected, res["answer"])
        rec.update({f"{tag}_status": "OK", f"{tag}_answer": res["answer"],
                    f"{tag}_latency_ms": res["latency_ms"],
                    f"{tag}_fact_coverage": _fact_coverage(expected, res["answer"]),
                    f"{tag}_facts_found": found, f"{tag}_facts_missing": missing,
                    f"{tag}_chunks_used": res.get("chunks_used", 0),
                    f"{tag}_sources": res.get("sources", [])})
        if tag == "v2":
            rec["v2_confidence"] = res.get("confidence", "")
            rec["v2_query_path"] = res.get("query_path", "")
            rec["v2_input_tokens"] = res.get("input_tokens", 0)
            rec["v2_output_tokens"] = res.get("output_tokens", 0)
        else:
            rec["v1_tokens_in"] = res.get("tokens_in", 0)
            rec["v1_tokens_out"] = res.get("tokens_out", 0)
    # Deltas
    if rec.get("v1_status") == "OK" and rec.get("v2_status") == "OK":
        rec["delta_latency_ms"] = rec["v2_latency_ms"] - rec["v1_latency_ms"]
        rec["delta_fact_coverage"] = rec["v2_fact_coverage"] - rec["v1_fact_coverage"]
        v1f, v2f = rec["v1_fact_coverage"], rec["v2_fact_coverage"]
        if v2f > v1f:
            rec["winner"] = "V2"
        elif v1f > v2f:
            rec["winner"] = "V1"
        else:
            rec["winner"] = ("V2" if rec["v2_latency_ms"] < rec["v1_latency_ms"]
                             else ("V1" if rec["v1_latency_ms"] < rec["v2_latency_ms"] else "TIE"))
    else:
        rec["delta_latency_ms"] = rec["delta_fact_coverage"] = None
        rec["winner"] = ("V2" if rec.get("v2_status") == "OK"
                         else ("V1" if rec.get("v1_status") == "OK" else "NONE"))
    return rec


def _print_table(records: list[dict], v1_avail: bool) -> None:
    sep = "-" * 110
    print(f"\n{sep}\n  V1 vs V2 COMPARISON\n{sep}")
    if v1_avail:
        print(f"{'ID':<8} {'V1 Facts':>9} {'V2 Facts':>9} {'V1 ms':>7} {'V2 ms':>7} {'Delta ms':>9} {'Winner':>7}  Query")
    else:
        print(f"{'ID':<8} {'V2 Facts':>9} {'V2 ms':>7} {'Conf':>6}  Query")
    print(sep)
    for r in records:
        q = r["query"][:42] + ("..." if len(r["query"]) > 42 else "")
        v2f = f"{r['v2_fact_coverage']:.0%}"
        if v1_avail:
            v1f = f"{r['v1_fact_coverage']:.0%}" if r["v1_status"] == "OK" else "N/A"
            v1l = f"{r['v1_latency_ms']}" if r["v1_status"] == "OK" else "N/A"
            dl = f"{r['delta_latency_ms']:+d}" if r["delta_latency_ms"] is not None else "N/A"
            print(f"{r['id']:<8} {v1f:>9} {v2f:>9} {v1l:>7} {r['v2_latency_ms']:>7} {dl:>9} {r['winner']:>7}  {q}")
        else:
            print(f"{r['id']:<8} {v2f:>9} {r['v2_latency_ms']:>7} {r.get('v2_confidence','')[:6]:>6}  {q}")
    print(sep)


def _print_summary(records: list[dict], v1_avail: bool) -> None:
    total = len(records)
    v2fc = sum(r["v2_fact_coverage"] for r in records) / max(total, 1)
    v2lat = sum(r["v2_latency_ms"] for r in records) / max(total, 1)
    print(f"\n  Total queries: {total}")
    print(f"  V2 avg fact coverage: {v2fc:.0%}")
    print(f"  V2 avg latency:      {v2lat:.0f}ms")
    if v1_avail:
        ok = [r for r in records if r["v1_status"] == "OK"]
        if ok:
            v1fc = sum(r["v1_fact_coverage"] for r in ok) / len(ok)
            v1lat = sum(r["v1_latency_ms"] for r in ok) / len(ok)
            v2ok = sum(r["v2_fact_coverage"] for r in ok) / len(ok)
            print(f"  V1 avg fact coverage: {v1fc:.0%}")
            print(f"  V1 avg latency:      {v1lat:.0f}ms")
            print(f"  V2 improvement:      fact_coverage {v2ok - v1fc:+.0%}  latency {v2lat - v1lat:+.0f}ms")
            wins = {"V1": 0, "V2": 0, "TIE": 0}
            for r in ok:
                wins[r["winner"]] = wins.get(r["winner"], 0) + 1
            print(f"  Wins: V1={wins['V1']}  V2={wins['V2']}  TIE={wins['TIE']}")
    # Per-type breakdown
    types: dict[str, list[dict]] = {}
    for r in records:
        types.setdefault(r["query_type"], []).append(r)
    print("\n  Per-query-type breakdown:")
    for qt in sorted(types):
        items = types[qt]
        afc = sum(r["v2_fact_coverage"] for r in items) / len(items)
        alat = sum(r["v2_latency_ms"] for r in items) / len(items)
        line = f"    {qt:<12} n={len(items):<3} V2 fact_cov={afc:.0%}  V2 lat={alat:.0f}ms"
        if v1_avail:
            ok_i = [r for r in items if r["v1_status"] == "OK"]
            if ok_i:
                line += f"  V1 fact_cov={sum(r['v1_fact_coverage'] for r in ok_i)/len(ok_i):.0%}"
        print(line)
    print()


def _generate_markdown(records: list[dict], v1_avail: bool, path: Path) -> None:
    total = len(records)
    v2fc = sum(r["v2_fact_coverage"] for r in records) / max(total, 1)
    v2lat = sum(r["v2_latency_ms"] for r in records) / max(total, 1)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L: list[str] = [f"# V1 vs V2 Comparison Report", "", f"Generated: {ts}", "",
                    "## Summary", ""]
    if v1_avail:
        ok = [r for r in records if r["v1_status"] == "OK"]
        v1fc = sum(r["v1_fact_coverage"] for r in ok) / max(len(ok), 1) if ok else 0
        v1lat = sum(r["v1_latency_ms"] for r in ok) / max(len(ok), 1) if ok else 0
        wins = {"V1": 0, "V2": 0, "TIE": 0}
        for r in ok:
            wins[r["winner"]] = wins.get(r["winner"], 0) + 1
        L += ["| Metric | V2 | V1 | Delta |", "|--------|----|----|-------|",
              f"| Fact Coverage | {v2fc:.0%} | {v1fc:.0%} | {v2fc-v1fc:+.0%} |",
              f"| Avg Latency | {v2lat:.0f}ms | {v1lat:.0f}ms | {v2lat-v1lat:+.0f}ms |",
              f"| Wins | {wins['V2']} | {wins['V1']} | TIE: {wins['TIE']} |"]
    else:
        L += ["| Metric | V2 |", "|--------|-----|",
              f"| Fact Coverage | {v2fc:.0%} |", f"| Avg Latency | {v2lat:.0f}ms |"]
    L += ["", "## Per-Query Results", ""]
    if v1_avail:
        L.append("| ID | Type | V1 Facts | V2 Facts | V1 ms | V2 ms | Winner |")
        L.append("|-----|------|----------|----------|-------|-------|--------|")
        for r in records:
            v1f = f"{r['v1_fact_coverage']:.0%}" if r["v1_status"] == "OK" else "N/A"
            v1l = str(r["v1_latency_ms"]) if r["v1_status"] == "OK" else "N/A"
            L.append(f"| {r['id']} | {r['query_type']} | {v1f} | {r['v2_fact_coverage']:.0%} | {v1l} | {r['v2_latency_ms']} | **{r['winner']}** |")
    else:
        L.append("| ID | Type | V2 Facts | V2 ms | Confidence |")
        L.append("|-----|------|----------|-------|------------|")
        for r in records:
            L.append(f"| {r['id']} | {r['query_type']} | {r['v2_fact_coverage']:.0%} | {r['v2_latency_ms']} | {r.get('v2_confidence','')} |")
    judged = [r for r in records if "judge" in r]
    if judged:
        L += ["", "## LLM Judge Results", "", "| ID | Preference | Reasoning |",
              "|-----|------------|-----------|"]
        for r in judged:
            j = r["judge"]
            L.append(f"| {r['id']} | **{j['preference']}** | {j['reasoning']} |")
    L.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")
    print(f"  Markdown report written to: {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="V1 vs V2 comparison harness")
    ap.add_argument("--v1", default="http://localhost:8000", help="V1 base URL")
    ap.add_argument("--v2", default="http://localhost:8001", help="V2 base URL")
    ap.add_argument("--v1-results", default=None, help="Pre-captured V1 results JSON")
    ap.add_argument("--judge", action="store_true", help="Enable GPT-4o pairwise judge")
    ap.add_argument("--report", default=None, help="Markdown report output path")
    ap.add_argument("--output", default=None, help="JSON output path")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if not GOLDEN_PATH.exists():
        print(f"ERROR: Golden queries not found at {GOLDEN_PATH}"); sys.exit(1)
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden_queries: list[dict] = json.load(f)

    # Offline V1 results
    v1_offline: dict[str, dict] | None = None
    if args.v1_results:
        v1_path = Path(args.v1_results)
        if not v1_path.is_absolute():
            v1_path = V2_ROOT / v1_path
        if not v1_path.exists():
            print(f"ERROR: V1 results not found: {v1_path}"); sys.exit(1)
        with open(v1_path, encoding="utf-8") as f:
            v1_data = json.load(f)
        v1_offline = {r["id"]: r for r in v1_data} if isinstance(v1_data, list) else v1_data
        print(f"  Loaded {len(v1_offline)} pre-captured V1 results from {v1_path}")

    # Probe V2 (fatal)
    try:
        with httpx.Client(timeout=5.0) as probe:
            probe.get(f"{args.v2.rstrip('/')}/health")
    except Exception as exc:
        print(f"FATAL: V2 at {args.v2} unreachable: {exc}"); sys.exit(1)

    # Probe V1 (warn only)
    v1_live = False
    if v1_offline is None:
        try:
            with httpx.Client(timeout=5.0) as probe:
                probe.get(f"{args.v1.rstrip('/')}/health")
            v1_live = True
        except Exception as exc:
            logger.warning("V1 at %s unreachable: %s -- V2-only mode", args.v1, exc)
    v1_avail = v1_live or v1_offline is not None

    print("=" * 60)
    print("  HybridRAG V1 vs V2 Comparison")
    print(f"  Queries: {len(golden_queries)}")
    print(f"  V1: {'offline file' if v1_offline else (args.v1 if v1_live else 'UNAVAILABLE')}")
    print(f"  V2: {args.v2}")
    if args.judge:
        print("  LLM Judge: ENABLED (GPT-4o)")
    print("=" * 60 + "\n")

    records: list[dict] = []
    client = httpx.Client(timeout=TIMEOUT)
    try:
        for i, qdef in enumerate(golden_queries, 1):
            qid, query_text = qdef["id"], qdef["query"]
            print(f"  [{i:>2}/{len(golden_queries)}] {qid}: {query_text[:50]}{'...' if len(query_text)>50 else ''}")
            # V1
            v1_result: dict | None = None
            if v1_offline is not None:
                raw = v1_offline.get(qid)
                if raw:
                    v1_result = {k: raw.get(f"v1_{k}", raw.get(k, d)) for k, d in
                                 [("status", "OK"), ("answer", ""), ("latency_ms", 0),
                                  ("chunks_used", 0), ("sources", []), ("tokens_in", 0), ("tokens_out", 0)]}
            elif v1_live:
                v1_result = _query_v1(client, args.v1, query_text)
            # V2
            v2_result = _query_v2(client, args.v2, query_text)
            rec = _score_query(qdef, v1_result, v2_result)
            # Judge
            if args.judge and v1_result and v2_result:
                v1a = v1_result.get("answer", "") if v1_result.get("status") == "OK" else ""
                v2a = v2_result.get("answer", "") if v2_result.get("status") == "OK" else ""
                if v1a and v2a:
                    rec["judge"] = _judge_pair(query_text, v1a, v2a)
                    print(f"           judge: {rec['judge']['preference']}")
            records.append(rec)
            v1s = f"V1={rec['v1_fact_coverage']:.0%}" if rec.get("v1_status") == "OK" else "V1=N/A"
            print(f"           {v1s}  V2={rec['v2_fact_coverage']:.0%}  winner={rec['winner']}")
    finally:
        client.close()

    _print_table(records, v1_avail)
    _print_summary(records, v1_avail)

    # JSON output
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output) if args.output else RESULTS_DIR / "v1_vs_v2_comparison.json"
    if not out_path.is_absolute():
        out_path = V2_ROOT / out_path
    payload: dict = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "v1_source": str(args.v1_results) if args.v1_results else (args.v1 if v1_live else "UNAVAILABLE"),
        "v2_source": args.v2, "total_queries": len(records),
        "v1_available": v1_avail, "judge_enabled": args.judge, "records": records,
        "v2_avg_fact_coverage": sum(r["v2_fact_coverage"] for r in records) / max(len(records), 1),
        "v2_avg_latency_ms": sum(r["v2_latency_ms"] for r in records) / max(len(records), 1),
    }
    if v1_avail:
        ok = [r for r in records if r.get("v1_status") == "OK"]
        if ok:
            payload["v1_avg_fact_coverage"] = sum(r["v1_fact_coverage"] for r in ok) / len(ok)
            payload["v1_avg_latency_ms"] = sum(r["v1_latency_ms"] for r in ok) / len(ok)
            v2ok_fc = sum(r["v2_fact_coverage"] for r in ok) / len(ok)
            payload["v2_improvement_fact_coverage"] = v2ok_fc - payload["v1_avg_fact_coverage"]
            payload["v2_improvement_latency_ms"] = payload["v2_avg_latency_ms"] - payload["v1_avg_latency_ms"]
            wins = {"V1": 0, "V2": 0, "TIE": 0}
            for r in ok:
                wins[r["winner"]] = wins.get(r["winner"], 0) + 1
            payload["wins"] = wins
    if args.judge:
        prefs: dict[str, int] = {"V1": 0, "V2": 0, "TIE": 0, "ERROR": 0, "SKIP": 0}
        for r in records:
            if "judge" in r:
                prefs[r["judge"]["preference"]] = prefs.get(r["judge"]["preference"], 0) + 1
        payload["judge_preferences"] = prefs
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"  JSON results written to: {out_path}")

    if args.report:
        rp = Path(args.report)
        if not rp.is_absolute():
            rp = V2_ROOT / args.report
        _generate_markdown(records, v1_avail, rp)

    print("\n  Done.")


if __name__ == "__main__":
    main()
