"""
Query Anchor Miner — reviewer — 2026-04-12

Read-only helper for building RAGAS-compatible evaluation queries grounded in
real corpus content. Pulls real anchors (sites, parts, POs, dates, people,
source paths) from the Tier 1 entity store and the LanceDB chunk store so
hand-authored queries reference real data instead of fictitious placeholders.

Design rules:
- Read-only on entities.sqlite3 (opened with mode=ro)
- Read-only on LanceDB (search via VectorRetriever / hybrid_search, no writes)
- No LLM calls for mining (cheap, deterministic, reproducible)
- Output is JSON to stdout or a file, easy to diff and re-run

Usage:
    python scripts/mine_query_anchors.py sites               # top SITE entities with counts
    python scripts/mine_query_anchors.py parts               # top PART entities (non-security standard)
    python scripts/mine_query_anchors.py pos                 # top PO entities
    python scripts/mine_query_anchors.py persons             # top PERSON entities
    python scripts/mine_query_anchors.py subtrees            # entity count by top-level subtree
    python scripts/mine_query_anchors.py folders --like "%Logistics%" --limit 30
    python scripts/mine_query_anchors.py chunks "part failure tracker" --top 5
    python scripts/mine_query_anchors.py ground-truth --query "..." --top 5

The `chunks` subcommand runs a real hybrid search against LanceDB and prints
the top results with source_path and a 200-char text preview -- exactly what
you need to mine ground-truth contexts for a proposed query.

Signed: reviewer | HybridRAG_V2 | 2026-04-12 MDT
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

v2_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(v2_root))

ENTITY_DB = v2_root / "data" / "index" / "entities.sqlite3"
LANCE_DB = v2_root / "data" / "index" / "lancedb"

# security standard RMF / control identifier prefixes that pollute the PART and PO columns
# in Tier 1 regex output. Exclude these to find real procurement data.
NIST_CONTROL_PREFIXES = (
    "CCI-", "SP-800", "AC-", "IR-", "SC-", "CM-", "CA-", "SV-", "AU-",
    "SI-", "AT-", "PE-", "PS-", "PL-", "RA-", "PM-", "IA-", "MP-", "MA-",
    "CP-", "SA-", "SP-", "IA-",
)


def _open_entity_db() -> sqlite3.Connection:
    """Support the mine query anchors workflow by handling the open entity db step."""
    return sqlite3.connect(f"file:{ENTITY_DB.as_posix()}?mode=ro", uri=True)


def _short_src(path: str) -> str:
    """Normalize raw text into a simpler form that is easier to compare or display."""
    if not path:
        return ""
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else path


def _is_nist_control(text: str) -> bool:
    """Support the mine query anchors workflow by handling the is security standard control step."""
    upper = (text or "").upper()
    return any(upper.startswith(p) for p in NIST_CONTROL_PREFIXES)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
def cmd_sites(args) -> None:
    """Top SITE entities with counts, filtered against template/placeholder noise."""
    conn = _open_entity_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT text, COUNT(*) as n
        FROM entities
        WHERE entity_type='SITE'
          AND text NOT LIKE '%[Insert%'
          AND text NOT LIKE '%TBD%'
          AND length(text) >= 4
        GROUP BY text
        ORDER BY n DESC
        LIMIT ?
        """,
        (args.limit,),
    )
    rows = cur.fetchall()
    conn.close()
    _emit(args, [{"text": t, "count": n} for t, n in rows])


def cmd_parts(args) -> None:
    """Top PART entities, filtering out security standard control identifiers."""
    conn = _open_entity_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT text, COUNT(*) as n
        FROM entities
        WHERE entity_type='PART'
          AND length(text) >= 3
        GROUP BY text
        ORDER BY n DESC
        LIMIT ?
        """,
        (args.limit * 4,),  # pull more, filter security standard, then trim
    )
    rows = [(t, n) for t, n in cur.fetchall() if not _is_nist_control(t)][: args.limit]
    conn.close()
    _emit(args, [{"text": t, "count": n} for t, n in rows])


def cmd_pos(args) -> None:
    """Top PO entities, filtering out security standard control identifiers."""
    conn = _open_entity_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT text, COUNT(*) as n
        FROM entities
        WHERE entity_type='PO'
          AND length(text) >= 3
        GROUP BY text
        ORDER BY n DESC
        LIMIT ?
        """,
        (args.limit * 4,),
    )
    rows = [(t, n) for t, n in cur.fetchall() if not _is_nist_control(t)][: args.limit]
    conn.close()
    _emit(args, [{"text": t, "count": n} for t, n in rows])


def cmd_persons(args) -> None:
    """Top PERSON entities."""
    conn = _open_entity_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT text, COUNT(*) as n
        FROM entities
        WHERE entity_type='PERSON'
          AND length(text) >= 4
        GROUP BY text
        ORDER BY n DESC
        LIMIT ?
        """,
        (args.limit,),
    )
    rows = cur.fetchall()
    conn.close()
    _emit(args, [{"text": t, "count": n} for t, n in rows])


def cmd_subtrees(args) -> None:
    """Entity count by top-level corpus subtree for each entity type."""
    conn = _open_entity_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            CASE
                WHEN source_path LIKE '%Logistics%' THEN 'Logistics'
                WHEN source_path LIKE '%Cybersecurity%' THEN 'Cybersecurity'
                WHEN source_path LIKE '%Program Management%' THEN 'Program Management'
                WHEN source_path LIKE '%Site Visits%' THEN 'Site Visits'
                WHEN source_path LIKE '%SysAdmin%' THEN 'SysAdmin'
                WHEN source_path LIKE '%Systems_Engineering%' THEN 'Systems Engineering'
                WHEN source_path LIKE '%monitoring system Sites%' THEN 'monitoring system Sites'
                WHEN source_path LIKE '%legacy monitoring system Sites%' THEN 'legacy monitoring system Sites'
                WHEN source_path LIKE '%CDRLS%' OR source_path LIKE '%enterprise program CDRLS%' THEN 'CDRLs'
                WHEN source_path LIKE '%Asset Management%' THEN 'Asset Mgmt'
                WHEN source_path LIKE '%Drawings%' THEN 'Drawings'
                WHEN source_path LIKE '%Deliverables Report%' THEN 'Deliverables (Compliance)'
                ELSE 'other'
            END as subtree,
            entity_type,
            COUNT(*) as n
        FROM entities
        WHERE entity_type IN ('SITE', 'PART', 'PO', 'PERSON', 'DATE', 'CONTACT')
        GROUP BY subtree, entity_type
        ORDER BY subtree, entity_type
        """
    )
    rows = cur.fetchall()
    conn.close()
    out = [{"subtree": r[0], "entity_type": r[1], "count": r[2]} for r in rows]
    _emit(args, out)


def cmd_folders(args) -> None:
    """Distinct source_path folders matching a LIKE pattern, with entity count."""
    conn = _open_entity_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT source_path, COUNT(*) as n
        FROM entities
        WHERE source_path LIKE ?
        GROUP BY source_path
        ORDER BY n DESC
        LIMIT ?
        """,
        (args.like, args.limit),
    )
    rows = cur.fetchall()
    conn.close()
    _emit(args, [{"source_path": r[0], "count": r[1]} for r in rows])


def cmd_chunks(args) -> None:
    """Hybrid search against LanceDB for top-N chunks matching a query string.

    This is the ground-truth mining path: give it a query concept and it
    returns the real chunks that would answer it, with source_path and text
    preview. Use the output as `reference_contexts` entries in RAGAS queries.
    """
    # Pin GPU 1 before torch imports. Then remap to logical cuda:0 so the
    # embedder's CUDA_VISIBLE_DEVICES re-read picks up the visible GPU.
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
    import torch  # noqa: F401
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"

    from src.store.lance_store import LanceStore
    from src.query.embedder import Embedder
    from src.query.vector_retriever import VectorRetriever

    store = LanceStore(str(LANCE_DB))
    embedder = Embedder(model_name="nomic-ai/nomic-embed-text-v1.5", dim=768, device="cuda")
    retriever = VectorRetriever(store, embedder, top_k=args.top)
    results = retriever.search(args.query, top_k=args.top)

    out = []
    for i, r in enumerate(results, 1):
        preview = " ".join((r.text or "").split())[:200]
        out.append(
            {
                "rank": i,
                "chunk_id": r.chunk_id or "",
                "source_path": r.source_path or "",
                "short_source": _short_src(r.source_path or ""),
                "score": float(r.score or 0.0),
                "text_preview": preview,
            }
        )
    _emit(args, out)
    store.close()


def cmd_ground_truth(args) -> None:
    """Alias for `chunks` -- same thing, clearer intent when authoring queries."""
    cmd_chunks(args)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def _emit(args, rows) -> None:
    """Support the mine query anchors workflow by handling the emit step."""
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False, default=str)
        print(f"wrote {len(rows)} rows -> {args.out}")
    else:
        print(json.dumps(rows, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    """Parse command-line inputs and run the main mine query anchors workflow."""
    parser = argparse.ArgumentParser(
        description="Query anchor miner for RAGAS-compatible eval query authoring"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, fn in (("sites", cmd_sites), ("parts", cmd_parts), ("pos", cmd_pos), ("persons", cmd_persons)):
        p = sub.add_parser(name, help=f"Top {name} from entity store (count-sorted, noise-filtered)")
        p.add_argument("--limit", type=int, default=30)
        p.add_argument("--out", type=str, default=None)
        p.set_defaults(func=fn)

    p = sub.add_parser("subtrees", help="Entity counts by top-level subtree")
    p.add_argument("--out", type=str, default=None)
    p.set_defaults(func=cmd_subtrees)

    p = sub.add_parser("folders", help="Top source_path folders matching a LIKE pattern")
    p.add_argument("--like", type=str, required=True)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--out", type=str, default=None)
    p.set_defaults(func=cmd_folders)

    p = sub.add_parser("chunks", help="Hybrid search LanceDB for ground-truth chunks")
    p.add_argument("query", type=str)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--out", type=str, default=None)
    p.set_defaults(func=cmd_chunks)

    p = sub.add_parser("ground-truth", help="Alias for chunks -- mines ground-truth contexts")
    p.add_argument("query", type=str)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--out", type=str, default=None)
    p.set_defaults(func=cmd_ground_truth)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
