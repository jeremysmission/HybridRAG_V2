"""
Near-duplicate chunk deduplication for CorpusForge exports.

Uses MinHash + LSH banding on word-level shingles to find near-duplicate
chunks, then keeps the best canonical chunk per cluster.

Usage:
  python scripts/minhash_dedup.py --source C:/CorpusForge/data/output/latest
  python scripts/minhash_dedup.py --source <export_dir> --output data/dedup/export_foo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.import_embedengine import load_export, resolve_export_dir


WORD_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass
class ClusterSummary:
    """Near-duplicate cluster summary for reporting."""

    canonical_index: int
    canonical_chunk_id: str
    canonical_source: str
    duplicate_count: int
    duplicate_chunk_ids: list[str]
    similarity_to_canonical: list[float]


class UnionFind:
    """Small disjoint-set helper for clustering duplicate candidates."""

    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            self.parent[root_left] = root_right
        elif self.rank[root_left] > self.rank[root_right]:
            self.parent[root_right] = root_left
        else:
            self.parent[root_right] = root_left
            self.rank[root_left] += 1


def normalize_tokens(text: str) -> list[str]:
    """Tokenize text into lowercase word-like units."""
    return WORD_RE.findall(text.lower())


def make_shingles(text: str, shingle_size: int) -> set[str]:
    """Build word shingles for MinHash."""
    tokens = normalize_tokens(text)
    if not tokens:
        return {"<empty>"}
    if len(tokens) <= shingle_size:
        return {" ".join(tokens)}
    return {
        " ".join(tokens[i:i + shingle_size])
        for i in range(len(tokens) - shingle_size + 1)
    }


def exact_jaccard(left: set[str], right: set[str]) -> float:
    """Exact Jaccard similarity for candidate verification."""
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def score_chunk(index: int, chunk: dict) -> tuple[float, int, int, int]:
    """Prefer high-quality, longer, earlier chunks as canonical representatives."""
    text = chunk.get("enriched_text") or chunk.get("text") or ""
    parse_quality = float(chunk.get("parse_quality", 1.0))
    chunk_index = int(chunk.get("chunk_index", 0))
    return (parse_quality, len(text), -chunk_index, -index)


def build_minhash(shingles: set[str], num_perm: int):
    """Create a MinHash signature for a shingle set."""
    try:
        from datasketch import MinHash
    except ImportError as exc:
        raise RuntimeError(
            "datasketch is not installed. Install requirements.txt first."
        ) from exc

    signature = MinHash(num_perm=num_perm)
    for shingle in sorted(shingles):
        signature.update(shingle.encode("utf-8"))
    return signature


def cluster_chunks(
    chunks: list[dict],
    *,
    threshold: float,
    shingle_size: int,
    num_perm: int,
    bands: int,
    rows_per_band: int,
) -> tuple[UnionFind, list[set[str]]]:
    """Build near-duplicate clusters with MinHashLSH."""
    try:
        from datasketch import MinHashLSH
    except ImportError as exc:
        raise RuntimeError(
            "datasketch is not installed. Install requirements.txt first."
        ) from exc

    if bands * rows_per_band != num_perm:
        raise ValueError(
            f"bands * rows_per_band must equal num_perm ({bands} * {rows_per_band} != {num_perm})"
        )

    union_find = UnionFind(len(chunks))
    shingle_cache: list[set[str]] = []
    lsh = MinHashLSH(
        threshold=threshold,
        num_perm=num_perm,
        params=(bands, rows_per_band),
    )

    for index, chunk in enumerate(chunks):
        text = chunk.get("enriched_text") or chunk.get("text") or ""
        shingles = make_shingles(text, shingle_size)
        signature = build_minhash(shingles, num_perm)

        for candidate in lsh.query(signature):
            candidate_index = int(candidate)
            similarity = exact_jaccard(shingles, shingle_cache[candidate_index])
            if similarity >= threshold:
                union_find.union(index, candidate_index)

        lsh.insert(str(index), signature)
        shingle_cache.append(shingles)

    return union_find, shingle_cache


def deduplicate_chunks(
    chunks: list[dict],
    vectors: np.ndarray,
    *,
    threshold: float,
    shingle_size: int,
    num_perm: int,
    bands: int,
    rows_per_band: int,
    sample_clusters: int,
) -> tuple[list[dict], np.ndarray, dict]:
    """Deduplicate chunks and return the kept subset plus a report."""
    union_find, shingle_cache = cluster_chunks(
        chunks,
        threshold=threshold,
        shingle_size=shingle_size,
        num_perm=num_perm,
        bands=bands,
        rows_per_band=rows_per_band,
    )

    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(chunks)):
        grouped[union_find.find(index)].append(index)

    keep_indices: list[int] = []
    cluster_summaries: list[ClusterSummary] = []
    duplicate_cluster_count = 0

    for members in grouped.values():
        canonical = max(members, key=lambda idx: score_chunk(idx, chunks[idx]))
        keep_indices.append(canonical)

        if len(members) == 1:
            continue

        duplicate_cluster_count += 1
        duplicates = sorted(idx for idx in members if idx != canonical)
        similarity_scores = [
            round(exact_jaccard(shingle_cache[canonical], shingle_cache[idx]), 4)
            for idx in duplicates
        ]
        cluster_summaries.append(
            ClusterSummary(
                canonical_index=canonical,
                canonical_chunk_id=chunks[canonical]["chunk_id"],
                canonical_source=chunks[canonical].get("source_path", ""),
                duplicate_count=len(duplicates),
                duplicate_chunk_ids=[chunks[idx]["chunk_id"] for idx in duplicates],
                similarity_to_canonical=similarity_scores,
            )
        )

    keep_indices = sorted(keep_indices)
    deduped_chunks = [chunks[idx] for idx in keep_indices]
    deduped_vectors = np.asarray(vectors[keep_indices])

    removed = len(chunks) - len(deduped_chunks)
    reduction_pct = (removed / len(chunks) * 100.0) if chunks else 0.0
    cluster_summaries.sort(key=lambda item: item.duplicate_count, reverse=True)

    report = {
        "input_chunks": len(chunks),
        "kept_chunks": len(deduped_chunks),
        "removed_chunks": removed,
        "reduction_pct": round(reduction_pct, 2),
        "duplicate_clusters": duplicate_cluster_count,
        "threshold": threshold,
        "shingle_size": shingle_size,
        "num_perm": num_perm,
        "bands": bands,
        "rows_per_band": rows_per_band,
        "sample_clusters": [
            {
                "canonical_chunk_id": item.canonical_chunk_id,
                "canonical_source": item.canonical_source,
                "duplicate_count": item.duplicate_count,
                "duplicate_chunk_ids": item.duplicate_chunk_ids,
                "similarity_to_canonical": item.similarity_to_canonical,
            }
            for item in cluster_summaries[:sample_clusters]
        ],
    }
    return deduped_chunks, deduped_vectors, report


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write JSONL with stable UTF-8 + LF semantics."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_export(
    output_dir: Path,
    *,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    skip_manifest: dict | None,
    report: dict,
) -> None:
    """Write a deduplicated export package."""
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "chunks.jsonl", chunks)
    np.save(str(output_dir / "vectors.npy"), vectors.astype(np.float16))
    write_jsonl(output_dir / "entities.jsonl", [])

    manifest_copy = dict(manifest) if manifest else {}
    stats = dict(manifest_copy.get("stats", {}))
    stats["minhash_dedup"] = report
    manifest_copy["stats"] = stats
    manifest_copy["chunk_count"] = len(chunks)
    manifest_copy["vector_dim"] = int(vectors.shape[1]) if vectors.ndim == 2 else 0
    manifest_copy["vector_dtype"] = str(vectors.dtype)
    manifest_copy["deduped"] = True

    with open(output_dir / "manifest.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest_copy, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    if skip_manifest:
        with open(output_dir / "skip_manifest.json", "w", encoding="utf-8", newline="\n") as handle:
            json.dump(skip_manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    with open(output_dir / "dedup_report.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main() -> None:
    """Parse command-line inputs and run the main minhash dedup workflow."""
    parser = argparse.ArgumentParser(description="MinHash deduplicate a CorpusForge export")
    parser.add_argument("--source", required=True, help="CorpusForge export directory or latest pointer file.")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output directory for a deduplicated export package.",
    )
    parser.add_argument("--threshold", type=float, default=0.8, help="Near-duplicate threshold.")
    parser.add_argument("--shingle-size", type=int, default=5, help="Word shingle size.")
    parser.add_argument(
        "--num-perm",
        type=int,
        default=100,
        help="MinHash permutations. Default aligns with 20 bands x 5 rows.",
    )
    parser.add_argument("--bands", type=int, default=20, help="LSH bands.")
    parser.add_argument("--rows-per-band", type=int, default=5, help="Rows per LSH band.")
    parser.add_argument(
        "--sample-clusters",
        type=int,
        default=25,
        help="How many duplicate clusters to include in the report sample.",
    )
    args = parser.parse_args()

    export_dir = resolve_export_dir(Path(args.source))
    if not export_dir.is_dir():
        print(f"ERROR: Export directory not found: {export_dir}", file=sys.stderr)
        sys.exit(1)

    chunks, vectors, manifest, skip_manifest = load_export(export_dir)
    print("=" * 60)
    print("  HybridRAG V2 -- MinHash Dedup")
    print("=" * 60)
    print(f"  Source:       {export_dir}")
    print(f"  Input chunks: {len(chunks):,}")
    print(f"  Threshold:    {args.threshold}")
    print(f"  Shingles:     {args.shingle_size}-gram words")
    print(f"  Signature:    {args.num_perm} perms ({args.bands} bands x {args.rows_per_band} rows)")
    print()

    deduped_chunks, deduped_vectors, report = deduplicate_chunks(
        chunks,
        vectors,
        threshold=args.threshold,
        shingle_size=args.shingle_size,
        num_perm=args.num_perm,
        bands=args.bands,
        rows_per_band=args.rows_per_band,
        sample_clusters=args.sample_clusters,
    )

    print(f"  Kept chunks:   {report['kept_chunks']:,}")
    print(f"  Removed:       {report['removed_chunks']:,}")
    print(f"  Reduction:     {report['reduction_pct']:.2f}%")
    print(f"  Dup clusters:  {report['duplicate_clusters']:,}")

    if args.output:
        output_dir = Path(args.output)
        write_export(
            output_dir,
            chunks=deduped_chunks,
            vectors=deduped_vectors,
            manifest=manifest,
            skip_manifest=skip_manifest,
            report=report,
        )
        print(f"  Output:        {output_dir}")

    print("=" * 60)


if __name__ == "__main__":
    main()
