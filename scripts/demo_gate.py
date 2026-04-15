"""
Sprint 8 demo gate harness.

Checks the promoted demo store, optional manifest-derived skip text, API health,
streaming contract, and a simple live smoke query against the configured server.

Default config is ``config/config.yaml`` (canonical current store). Legacy
sprintN demo configs pointed at ``data/index/sprint6/lancedb`` which is a stale
store and should not be targeted by a bare invocation. Pass ``--config`` to
override if a legacy sprint config is intentionally required.

Usage:
    python scripts/demo_gate.py
    python scripts/demo_gate.py --start-server
    python scripts/demo_gate.py --config config/config.sprint8_demo.yaml  # legacy override
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.demo_rehearsal import DEMO_QUERIES
from src.config.schema import load_config
from src.store.entity_store import EntityStore
from src.store.lance_store import LanceStore
from src.store.relationship_store import RelationshipStore


def _warn_if_sprint6_lance(config_path: str) -> None:
    """Warn loudly when the resolved config points at a legacy sprint6 Lance store."""
    try:
        resolved = load_config(config_path)
    except Exception:
        return
    lance_db = getattr(resolved.paths, "lance_db", "") or ""
    if "sprint6" in lance_db.lower():
        bar = "=" * 72
        print(bar, file=sys.stderr)
        print("WARNING: explicit config points at a legacy sprint6 Lance store.", file=sys.stderr)
        print(f"  config:    {config_path}", file=sys.stderr)
        print(f"  lance_db:  {lance_db}", file=sys.stderr)
        print("  This store is stale. Proceeding only because --config was", file=sys.stderr)
        print("  supplied explicitly. Use the default config to target the", file=sys.stderr)
        print("  canonical current store.", file=sys.stderr)
        print(bar, file=sys.stderr)


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def wait_for_health(base_url: str, timeout_seconds: float = 60.0) -> dict:
    """Wait until the API health endpoint responds successfully."""
    deadline = time.time() + timeout_seconds
    last_error = "health endpoint not reached"
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{base_url.rstrip('/')}/health")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1.0)
    raise TimeoutError(f"V2 API at {base_url} did not become healthy: {last_error}")


def start_server_process(config_path: str, host: str, port: int) -> subprocess.Popen:
    """Start the V2 API server as a child process."""
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "src.api.server",
            "--config",
            config_path,
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
    )


def summarize_store(config_path: str) -> dict:
    """Collect store and index readiness stats for the configured demo store."""
    config = load_config(config_path)
    store = LanceStore(config.paths.lance_db)
    entity_store = EntityStore(config.paths.entity_db)
    relationship_store = RelationshipStore(config.paths.entity_db)
    try:
        return {
            "lance_path": config.paths.lance_db,
            "entity_path": config.paths.entity_db,
            "chunks": store.count(),
            "vector_index_present": store.has_vector_index(),
            "vector_index_stats": store.vector_index_stats(),
            "vector_index_ready": store.vector_index_ready(),
            "entities": entity_store.count_entities(),
            "table_rows": entity_store.count_table_rows(),
            "relationships": relationship_store.count(),
        }
    finally:
        store.close()
        entity_store.close()
        relationship_store.close()


def build_skip_ack(manifest_path: Path | None, skip_manifest_path: Path | None) -> dict:
    """Build operator-facing skip acknowledgment text from available manifests."""
    if manifest_path is None or not manifest_path.exists():
        return {
            "available": False,
            "text": "No manifest provided. Supply --manifest to generate the skip-file acknowledgment.",
        }

    manifest = load_json(manifest_path)
    stats = manifest.get("stats", {})
    files_found = int(stats.get("files_found", 0))
    files_parsed = int(stats.get("files_parsed", 0))
    chunks_created = int(stats.get("chunks_created", manifest.get("chunk_count", 0)))
    parse_failures = max(files_found - files_parsed, 0) if files_found else 0

    skipped = 0
    reasons: dict[str, int] = {}
    if skip_manifest_path and skip_manifest_path.exists():
        skip_manifest = load_json(skip_manifest_path)
        skipped = int(skip_manifest.get("total_skipped", 0))
        reasons = {
            str(key): int(value)
            for key, value in (skip_manifest.get("counts_by_reason", {}) or {}).items()
        }

    if reasons:
        reason_text = ", ".join(f"{count} {reason}" for reason, count in sorted(reasons.items()))
        final_line = (
            f"Deferred formats currently tracked in the skip manifest: {skipped} files "
            f"({reason_text})."
        )
    else:
        final_line = (
            "Full-corpus deferred categories still include CAD, encrypted, and skip-list "
            "formats, and those are being tracked rather than silently dropped."
        )

    text = (
        f"For the current proof subset, {files_found} supported files were staged. "
        f"{files_parsed} parsed successfully and produced {chunks_created:,} raw chunks. "
        f"{parse_failures} files failed parsing and remain tracked for follow-up. "
        f"{final_line}"
    )
    return {
        "available": True,
        "manifest_path": str(manifest_path),
        "skip_manifest_path": str(skip_manifest_path) if skip_manifest_path else "",
        "files_found": files_found,
        "files_parsed": files_parsed,
        "parse_failures": parse_failures,
        "chunks_created": chunks_created,
        "skipped": skipped,
        "reasons": reasons,
        "text": text,
    }


def probe_health(base_url: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{base_url.rstrip('/')}/health")
        resp.raise_for_status()
        return resp.json()


def probe_query(base_url: str, query_number: int) -> dict:
    """Run a simple live query and score it against the demo expectations."""
    demo_query = next((item for item in DEMO_QUERIES if item.number == query_number), None)
    if demo_query is None:
        raise ValueError(f"Demo query {query_number} is not defined.")

    payload = {"query": demo_query.query, "top_k": 10}
    start = time.perf_counter()
    with httpx.Client(timeout=180.0) as client:
        resp = client.post(f"{base_url.rstrip('/')}/query", json=payload)
    latency_ms = int((time.perf_counter() - start) * 1000)
    body = resp.json()
    answer = body.get("answer", "")
    answer_upper = answer.upper()
    facts_found = [fact for fact in demo_query.expected_facts if fact.upper() in answer_upper]
    facts_missing = [fact for fact in demo_query.expected_facts if fact.upper() not in answer_upper]
    return {
        "status_code": resp.status_code,
        "query_number": query_number,
        "title": demo_query.title,
        "query": demo_query.query,
        "latency_ms": body.get("latency_ms", latency_ms),
        "confidence": body.get("confidence", ""),
        "query_path": body.get("query_path", ""),
        "facts_found": facts_found,
        "facts_missing": facts_missing,
        "confidence_ok": body.get("confidence", "") == demo_query.expected_confidence,
        "path_ok": body.get("query_path", "") == demo_query.expected_path,
        "facts_ok": len(facts_missing) == 0,
    }


def probe_stream(base_url: str, query_number: int) -> dict:
    """Verify SSE event order for one representative query."""
    demo_query = next((item for item in DEMO_QUERIES if item.number == query_number), None)
    if demo_query is None:
        raise ValueError(f"Demo query {query_number} is not defined.")

    payload = {"query": demo_query.query, "top_k": 10}
    events: list[dict] = []
    token_count = 0

    with httpx.Client(timeout=180.0) as client:
        with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/query/stream",
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    events.append({"type": "DONE"})
                    break
                event = json.loads(data)
                events.append(event)
                if event.get("type") == "token":
                    token_count += 1

    metadata = next((event for event in events if event.get("type") == "metadata"), None)
    done = next((event for event in events if event.get("type") == "done"), None)
    event_types = [event.get("type", "DONE") for event in events]
    metadata_first = bool(events) and events[0].get("type") == "metadata"
    done_before_done = len(events) >= 2 and events[-2].get("type") == "done" and events[-1].get("type") == "DONE"
    return {
        "query_number": query_number,
        "event_types": event_types,
        "metadata_first": metadata_first,
        "done_emitted": done is not None,
        "done_before_stream_end": done_before_done,
        "token_count": token_count,
        "metadata": metadata,
        "done": done,
    }


def print_report(report: dict) -> None:
    """Render a readable demo-gate report."""
    print("=" * 72)
    print("  Sprint 8 Demo Gate")
    print("=" * 72)

    store = report["store"]
    print("\nStore")
    print(f"  Chunks:        {store['chunks']}")
    print(f"  Vector index:  {'present' if store['vector_index_present'] else 'absent'}")
    print(f"  Index ready:   {store['vector_index_ready']}")
    stats = store.get("vector_index_stats") or {}
    if stats:
        print(f"  Indexed rows:  {stats.get('num_indexed_rows')}")
        print(f"  Unindexed:     {stats.get('num_unindexed_rows')}")
        print(f"  Index type:    {stats.get('index_type')}")
    print(f"  Entities:      {store['entities']}")
    print(f"  Relationships: {store['relationships']}")

    ack = report["skip_ack"]
    print("\nSkip Ack")
    print(f"  Available:     {ack['available']}")
    print(f"  Text:          {ack['text']}")

    if "health" in report:
        health = report["health"]
        print("\nAPI Health")
        print(f"  Status:        {health.get('status')}")
        print(f"  Chunks loaded: {health.get('chunks_loaded')}")
        print(f"  Entities:      {health.get('entities_loaded')}")
        print(f"  LLM ready:     {health.get('llm_available')}")

    if "query" in report:
        query = report["query"]
        print("\nQuery Smoke")
        print(f"  Query:         Q{query['query_number']} {query['title']}")
        print(f"  Status code:   {query['status_code']}")
        print(f"  Confidence:    {query['confidence']} ({query['confidence_ok']})")
        print(f"  Path:          {query['query_path']} ({query['path_ok']})")
        print(f"  Facts OK:      {query['facts_ok']}")
        print(f"  Latency ms:    {query['latency_ms']}")
        if query["facts_missing"]:
            print(f"  Facts missing: {', '.join(query['facts_missing'])}")

    if "stream" in report:
        stream = report["stream"]
        print("\nStream")
        print(f"  Metadata first:    {stream['metadata_first']}")
        print(f"  Done emitted:      {stream['done_emitted']}")
        print(f"  Done before end:   {stream['done_before_stream_end']}")
        print(f"  Token count:       {stream['token_count']}")
        print(f"  Event types:       {', '.join(stream['event_types'])}")

    print("\nVerdict")
    print(f"  {report['verdict']}")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint 8 demo gate harness.")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help=(
            "Config YAML path. Defaults to config/config.yaml (canonical current "
            "store). Pass a legacy sprintN demo config only if that specific "
            "store is intentionally required."
        ),
    )
    parser.add_argument("--server-url", default=None, help="Override API base URL.")
    parser.add_argument("--start-server", action="store_true", help="Start the V2 API server for this run.")
    parser.add_argument("--server-timeout", type=float, default=90.0, help="Seconds to wait for API health.")
    parser.add_argument("--manifest", default=None, help="Primary CorpusForge manifest.json for skip text.")
    parser.add_argument("--skip-manifest", default=None, help="Optional skip_manifest.json for deferred counts.")
    parser.add_argument("--query-number", type=int, default=1, help="Demo query number for live smoke check.")
    parser.add_argument("--stream-query-number", type=int, default=1, help="Demo query number for SSE probe.")
    parser.add_argument("--skip-api", action="store_true", help="Skip API health/query/stream checks.")
    parser.add_argument("--skip-query", action="store_true", help="Skip live smoke query.")
    parser.add_argument("--skip-stream", action="store_true", help="Skip SSE probe.")
    parser.add_argument("--json-output", default=None, help="Optional JSON report path.")
    args = parser.parse_args()

    _warn_if_sprint6_lance(args.config)

    config = load_config(args.config)
    base_url = args.server_url or f"http://{config.server.host}:{config.server.port}"

    report: dict = {
        "config": args.config,
        "server_url": base_url,
        "store": summarize_store(args.config),
        "skip_ack": build_skip_ack(
            Path(args.manifest) if args.manifest else None,
            Path(args.skip_manifest) if args.skip_manifest else None,
        ),
    }

    server_process: subprocess.Popen | None = None
    try:
        if args.start_server and not args.skip_api:
            server_process = start_server_process(args.config, config.server.host, config.server.port)
            wait_for_health(base_url, timeout_seconds=args.server_timeout)

        if not args.skip_api:
            report["health"] = probe_health(base_url)
            if not args.skip_query:
                report["query"] = probe_query(base_url, args.query_number)
            if not args.skip_stream:
                report["stream"] = probe_stream(base_url, args.stream_query_number)
    finally:
        if server_process is not None:
            server_process.terminate()
            try:
                server_process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                server_process.kill()

    store_ready = report["store"]["chunks"] > 0 and report["store"]["vector_index_ready"] is True
    api_ready = True
    if not args.skip_api:
        health = report.get("health", {})
        query = report.get("query")
        stream = report.get("stream")
        api_ready = bool(health.get("status") == "ok")
        if query is not None:
            api_ready = api_ready and bool(
                query["status_code"] == 200
                and query["facts_ok"]
                and query["confidence_ok"]
                and query["path_ok"]
            )
        if stream is not None:
            api_ready = api_ready and bool(
                stream["metadata_first"]
                and stream["done_emitted"]
                and stream["done_before_stream_end"]
            )

    report["verdict"] = "PASS" if store_ready and api_ready else "FAIL"

    if args.json_output:
        output_path = Path(args.json_output)
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print_report(report)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
