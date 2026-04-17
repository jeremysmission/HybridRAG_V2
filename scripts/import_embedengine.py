"""
Import CorpusForge export into HybridRAG V2 LanceDB store.

Reads chunks.jsonl + vectors.npy + manifest.json from a CorpusForge export
directory and loads them into the vector store with FTS indexing.

Usage:
  python scripts/import_embedengine.py --source C:/CorpusForge/data/export/export_YYYYMMDD_HHMM
  python scripts/import_embedengine.py --source path/to/export --dry-run
  python scripts/import_embedengine.py --source path/to/export --create-index
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.schema import load_config
from src.store.lance_store import LanceStore
from src.store.retrieval_metadata_store import (
    RetrievalMetadataStore,
    derive_source_metadata,
    resolve_retrieval_metadata_db_path,
)


DIVIDER = "=" * 55

# Required fields in every chunk — import rejects chunks missing any of these
REQUIRED_CHUNK_FIELDS = ("chunk_id", "text", "source_path")

# Minimum manifest schema version that V2 can consume
MIN_SCHEMA_VERSION = 1


def validate_manifest(manifest: dict, vectors: np.ndarray) -> list[str]:
    """
    Validate manifest metadata against the loaded export.

    Returns a list of warning/error strings. Empty list = all good.
    """
    issues = []

    # Schema version gate — support both "schema_version" (int) and "version" (str like "1.0")
    schema_ver = manifest.get("schema_version")
    if schema_ver is None:
        ver_str = manifest.get("version")
        if ver_str is not None:
            try:
                schema_ver = int(float(ver_str))
            except (ValueError, TypeError):
                pass
    if schema_ver is not None and schema_ver < MIN_SCHEMA_VERSION:
        issues.append(
            f"REJECT: manifest schema_version={schema_ver} < minimum {MIN_SCHEMA_VERSION}"
        )

    # Vector dimension cross-check
    manifest_dim = manifest.get("vector_dim")
    if manifest_dim is not None and manifest_dim != vectors.shape[1]:
        issues.append(
            f"REJECT: manifest vector_dim={manifest_dim} but vectors.npy has dim={vectors.shape[1]}"
        )

    # Chunk count cross-check (warning, not rejection — partial exports exist)
    manifest_count = manifest.get("chunk_count")
    if manifest_count is not None and manifest_count != vectors.shape[0]:
        issues.append(
            f"WARNING: manifest chunk_count={manifest_count} but vectors.npy has {vectors.shape[0]} rows"
        )

    return issues


def validate_chunks(chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Validate each chunk has required fields with non-empty values.

    Returns:
        (valid_chunks, rejected_chunks)
    """
    valid = []
    rejected = []
    for i, chunk in enumerate(chunks):
        missing = [f for f in REQUIRED_CHUNK_FIELDS if not chunk.get(f)]
        if missing:
            rejected.append({"index": i, "chunk": chunk, "missing": missing})
        else:
            valid.append(chunk)
    return valid, rejected


def resolve_export_dir(source: Path) -> Path:
    """Resolve source path, following text-file redirects if needed."""
    if source.is_file() and source.suffix not in (".jsonl", ".npy", ".json"):
        # Text file pointing to real export dir
        real_path = source.read_text(encoding="utf-8-sig").strip()
        return Path(real_path)
    return source


def _matches_any_glob(source_path: str, patterns: list[str]) -> bool:
    """Return True if any glob pattern matches the source_path basename
    or any path component (case-insensitive). Used by the temporary
    --exclude-source-glob fallback for the Sprint 6.6 archive leak.
    """
    if not patterns:
        return False
    import fnmatch
    sp = source_path.replace("\\", "/").lower()
    base = sp.rsplit("/", 1)[-1]
    for pat in patterns:
        p = pat.lower()
        if fnmatch.fnmatch(base, p):
            return True
        if fnmatch.fnmatch(sp, p):
            return True
        # also match anywhere in the path components
        for component in sp.split("/"):
            if fnmatch.fnmatch(component, p):
                return True
    return False


def apply_exclude_source_globs(
    chunks: list[dict],
    vectors: np.ndarray,
    exclude_globs: list[str],
) -> tuple[list[dict], np.ndarray, int]:
    """
    TEMPORARY MORNING FALLBACK (Sprint 6.6, 2026-04-09)

    Drop any chunk whose ``source_path`` matches one of the supplied glob
    patterns. Designed as the operator-controlled safety net for the
    CorpusForge archive-defer leak: until a clean rerun is verified,
    operators can pass ``--exclude-source-glob "*.SAO.zip"`` /
    ``"*.RSF.zip"`` to exclude leaked ionogram chunks at import time.

    The corresponding rows are removed from ``vectors`` so the chunk and
    vector arrays stay aligned.

    Returns:
        (kept_chunks, kept_vectors, excluded_count)

    REMOVAL CONDITION: retire this filter once the archive_parser fix is
    verified by a clean rerun and the SAO leak is confirmed at zero in
    the new export.
    """
    if not exclude_globs:
        return chunks, vectors, 0

    keep_indices: list[int] = []
    excluded = 0
    for i, c in enumerate(chunks):
        sp = c.get("source_path", "")
        if _matches_any_glob(sp, exclude_globs):
            excluded += 1
        else:
            keep_indices.append(i)

    if excluded == 0:
        return chunks, vectors, 0

    kept_chunks = [chunks[i] for i in keep_indices]
    if isinstance(vectors, np.memmap):
        # Materialize from memmap into a regular array.
        kept_vectors = np.array(vectors[keep_indices])
    else:
        kept_vectors = vectors[keep_indices]
    return kept_chunks, kept_vectors, excluded


def load_export(export_dir: Path, strict: bool = False) -> tuple[list[dict], np.ndarray, dict, dict | None]:
    """
    Load chunks, vectors, manifest, and optional skip_manifest
    from a CorpusForge export directory.

    Returns:
        (chunks, vectors, manifest, skip_manifest_or_None)
    """
    export_dir = resolve_export_dir(export_dir)

    chunks_path = export_dir / "chunks.jsonl"
    vectors_path = export_dir / "vectors.npy"
    manifest_path = export_dir / "manifest.json"
    skip_manifest_path = export_dir / "skip_manifest.json"

    # Validate required files
    missing = []
    if not chunks_path.exists():
        missing.append(str(chunks_path))
    if not vectors_path.exists():
        missing.append(str(vectors_path))
    if missing:
        for m in missing:
            print(f"  ERROR: Required file not found: {m}", file=sys.stderr)
        sys.exit(1)

    # Load chunks
    chunks = []
    with open(chunks_path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    # Load vectors — memory-map large files to avoid OOM on multi-GB arrays
    vec_file_bytes = vectors_path.stat().st_size
    MMAP_THRESHOLD = 500 * 1024 * 1024  # 500 MB
    if vec_file_bytes > MMAP_THRESHOLD:
        print(f"  vectors.npy is {vec_file_bytes / (1024**3):.1f} GB — using memory-mapped I/O")
        vectors = np.load(str(vectors_path), mmap_mode="r")
    else:
        vectors = np.load(str(vectors_path))

    if vectors.shape[0] != len(chunks):
        print(
            f"  ERROR: Chunk/vector count mismatch — "
            f"{len(chunks)} chunks vs {vectors.shape[0]} vectors.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load manifest (optional but expected)
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8-sig") as f:
            manifest = json.load(f)

    # --- Manifest validation ---
    manifest_issues = validate_manifest(manifest, vectors)
    rejections = [i for i in manifest_issues if i.startswith("REJECT")]
    warnings = [i for i in manifest_issues if i.startswith("WARNING")]
    for w in warnings:
        print(f"  {w}", file=sys.stderr)
    if rejections:
        for r in rejections:
            print(f"  {r}", file=sys.stderr)
        print("  Import aborted due to manifest validation failure.", file=sys.stderr)
        sys.exit(1)

    # --- Chunk field validation ---
    valid_chunks, rejected_chunks = validate_chunks(chunks)
    if rejected_chunks:
        print(
            f"  WARNING: {len(rejected_chunks)} chunks rejected — missing required fields",
            file=sys.stderr,
        )
        # Write rejection log for operator review
        reject_log = export_dir / "import_rejected_chunks.jsonl"
        with open(reject_log, "w", encoding="utf-8") as rf:
            for entry in rejected_chunks:
                rf.write(json.dumps({
                    "index": entry["index"],
                    "chunk_id": entry["chunk"].get("chunk_id", "MISSING"),
                    "missing_fields": entry["missing"],
                    "source_path": entry["chunk"].get("source_path", "MISSING"),
                }, ensure_ascii=False) + "\n")
        print(f"  Rejection log: {reject_log}", file=sys.stderr)

        if strict:
            print(
                f"  STRICT MODE: aborting import — {len(rejected_chunks)} chunks failed validation.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Rebuild vectors to match valid-only chunks
        valid_indices = [i for i in range(len(chunks)) if not any(
            r["index"] == i for r in rejected_chunks
        )]
        vectors = np.array(vectors[valid_indices])
        chunks = valid_chunks

    # Load skip manifest (optional)
    skip_manifest = None
    if skip_manifest_path.exists():
        with open(skip_manifest_path, encoding="utf-8-sig") as f:
            skip_manifest = json.load(f)

    return chunks, vectors, manifest, skip_manifest


def prepare_streaming_import(
    export_dir: Path,
) -> tuple[Path, np.ndarray, dict, dict | None, int]:
    """Prepare a streaming import without loading chunks into memory.

    The walk-away GUI path previously called ``load_export`` which pulls the
    full chunks.jsonl into a Python list. On a 10M chunk export that pushed
    peak RSS past 30 GB before a single row reached LanceDB. This helper
    validates the manifest, memory-maps vectors.npy, and returns the paths
    and handles a streaming caller needs -- nothing more.

    Returns:
        (chunks_path, vectors_memmap, manifest, skip_manifest, total_chunks)
    """
    export_dir = resolve_export_dir(export_dir)

    chunks_path = export_dir / "chunks.jsonl"
    vectors_path = export_dir / "vectors.npy"
    manifest_path = export_dir / "manifest.json"
    skip_manifest_path = export_dir / "skip_manifest.json"

    missing = []
    if not chunks_path.exists():
        missing.append(str(chunks_path))
    if not vectors_path.exists():
        missing.append(str(vectors_path))
    if missing:
        for m in missing:
            print(f"  ERROR: Required file not found: {m}", file=sys.stderr)
        sys.exit(1)

    # Always memmap -- streaming callers read one batch at a time.
    vectors = np.load(str(vectors_path), mmap_mode="r")
    total_chunks = int(vectors.shape[0])

    manifest: dict = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8-sig") as f:
            manifest = json.load(f)

    issues = validate_manifest(manifest, vectors)
    rejections = [i for i in issues if i.startswith("REJECT")]
    warnings = [i for i in issues if i.startswith("WARNING")]
    for w in warnings:
        print(f"  {w}", file=sys.stderr)
    if rejections:
        for r in rejections:
            print(f"  {r}", file=sys.stderr)
        print("  Import aborted due to manifest validation failure.", file=sys.stderr)
        sys.exit(1)

    skip_manifest: dict | None = None
    if skip_manifest_path.exists():
        with open(skip_manifest_path, encoding="utf-8-sig") as f:
            skip_manifest = json.load(f)

    return chunks_path, vectors, manifest, skip_manifest, total_chunks


def stream_export_batches(
    chunks_path: Path,
    vectors: np.ndarray,
    batch_size: int = 1000,
):
    """Yield ``(chunk_list, vector_ndarray)`` pairs from an export.

    chunks.jsonl is read line-by-line so peak RSS is bounded to roughly
    ``batch_size`` chunks. Vectors are sliced out of the memory-mapped array
    and copied into a regular ndarray so the caller can freely convert to
    float32 / lists without holding the memmap open on that range.

    Skips blank lines and JSONDecodeError lines (logged via stderr) so a
    single corrupt row in a multi-million-line export does not abort an
    overnight walk-away run. Caller is expected to verify integrity after.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    batch: list[dict] = []
    batch_start_index = 0
    line_index = 0

    with open(chunks_path, encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                print(
                    f"  WARNING: skip malformed chunks.jsonl line "
                    f"{line_index}: {exc}",
                    file=sys.stderr,
                )
                line_index += 1
                continue
            batch.append(chunk)
            line_index += 1
            if len(batch) >= batch_size:
                end = batch_start_index + len(batch)
                vec_slice = np.array(vectors[batch_start_index:end])
                yield batch, vec_slice
                batch_start_index = end
                batch = []

    if batch:
        end = batch_start_index + len(batch)
        vec_slice = np.array(vectors[batch_start_index:end])
        yield batch, vec_slice


def print_export_summary(
    export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    skip_manifest: dict | None,
) -> None:
    """Print details about the export being imported."""
    print(f"  Source:     {export_dir}")
    print(f"  Chunks:     {len(chunks):,}")
    print(f"  Vectors:    {vectors.shape[0]:,} x {vectors.shape[1]}d")
    if manifest:
        print(f"  Model:      {manifest.get('embedding_model', 'unknown')}")
        print(f"  Created:    {manifest.get('timestamp', 'unknown')}")
        if "corpus_name" in manifest:
            print(f"  Corpus:     {manifest['corpus_name']}")

    # Sprint 6.6 morning fallback: surface active import-side filters in
    # the operator-visible summary so a filtered import does not look the
    # same as an unfiltered one.
    filters = (manifest or {}).get("import_filters") or {}
    if filters:
        print(f"  Filters:    --exclude-source-glob (TEMPORARY Sprint 6.6 fallback)")
        for g in filters.get("exclude_source_globs", []):
            print(f"              - {g}")
        pre = filters.get("pre_filter_chunk_count")
        post = filters.get("post_filter_chunk_count")
        excl = filters.get("excluded_chunk_count")
        if pre is not None and post is not None and excl is not None:
            print(
                f"              {excl:,} excluded, {post:,} kept "
                f"({pre:,} -> {post:,})"
            )
        reason = filters.get("filter_reason")
        if reason:
            print(f"              reason: {reason}")
        retire = filters.get("retire_when")
        if retire:
            print(f"              retire when: {retire}")

    # Unique source files in the export
    source_files = {c.get("source_path", "") for c in chunks}
    source_files.discard("")
    if source_files:
        print(f"  Files:      {len(source_files):,} unique source documents")

    # Skip manifest summary — operator-visible deferred/placeholder disclosure
    if skip_manifest:
        skipped = skip_manifest.get("skipped_files", [])
        count = len(skipped) if isinstance(skipped, list) else skip_manifest.get("count", 0)
        print(f"  Skipped:    {count} files were skipped during corpus processing")

        # Break down by skip reason if available
        if isinstance(skipped, list) and skipped:
            reason_counts: dict[str, int] = {}
            for entry in skipped:
                reason = entry.get("reason", "unknown") if isinstance(entry, dict) else "unknown"
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            for reason, cnt in sorted(reason_counts.items(), key=lambda x: -x[1]):
                print(f"              {reason}: {cnt}")

        # Deferred format families
        deferred = skip_manifest.get("deferred_formats", [])
        if deferred:
            print(f"  Deferred:   {len(deferred)} format families deferred (not yet parseable)")
            for fmt in deferred[:10]:
                ext = fmt.get("extension", fmt) if isinstance(fmt, dict) else fmt
                cnt = fmt.get("count", "?") if isinstance(fmt, dict) else "?"
                print(f"              .{ext}: {cnt} files")
            if len(deferred) > 10:
                print(f"              ... and {len(deferred) - 10} more")

        print(f"              -- see skip_manifest.json for full details")


def write_import_report(
    export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    mode: str,
    target_db: str | Path | None,
) -> Path:
    """Write a durable record of this import (or dry-run) into the export
    directory itself, so later operators can prove from an artifact which
    filters were active at import time and what got into V2.

    Filename: ``import_report_<timestamp>_<mode>.json``

    Includes:
        - timestamp + mode (dry_run or import)
        - target LanceDB path
        - source export path
        - final chunk + vector counts after any filtering
        - import_filters block (the Sprint 6.6 morning fallback record)
        - manifest fingerprint (model, original timestamp, original count)
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = export_dir / f"import_report_{timestamp}_{mode}.json"

    filters = (manifest or {}).get("import_filters") or {}
    report = {
        "import_report_version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "source_export_dir": str(export_dir),
        "target_db": str(target_db) if target_db is not None else None,
        "final_chunk_count": len(chunks),
        "final_vector_count": int(vectors.shape[0]),
        "vector_dim": int(vectors.shape[1]) if vectors.ndim == 2 else 0,
        "import_filters": filters,
        "source_manifest_fingerprint": {
            "embedding_model": (manifest or {}).get("embedding_model"),
            "original_timestamp": (manifest or {}).get("timestamp"),
            "original_chunk_count": (manifest or {}).get("chunk_count"),
        },
    }
    try:
        with open(report_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Import report written: {report_path}")
    except OSError as exc:
        # Don't let a report-write failure abort the import.
        print(f"  WARNING: failed to write import report at {report_path}: {exc}", file=sys.stderr)
    return report_path


def _print_metadata_summary(metadata_db: Path, summary: dict[str, int]) -> None:
    """Show operator-visible typed metadata coverage for this export/import."""
    print(f"  Metadata DB: {metadata_db}")
    print(f"  Metadata:   {summary.get('source_count', 0):,} source rows upserted")
    print(
        "              "
        f"cdrl={summary.get('with_cdrl_code', 0):,}, "
        f"incident={summary.get('with_incident_id', 0):,}, "
        f"po={summary.get('with_po_number', 0):,}, "
        f"contract={summary.get('with_contract_number', 0):,}, "
        f"site={summary.get('with_site', 0):,}"
    )
    print(
        "              "
        f"reference_dids={summary.get('reference_dids', 0):,}, "
        f"filed_deliverables={summary.get('filed_deliverables', 0):,}"
    )
    print(
        "              "
        f"contract_period={summary.get('with_contract_period', 0):,}, "
        f"program={summary.get('with_program_name', 0):,}, "
        f"doc_type={summary.get('with_document_type', 0):,}, "
        f"doc_category={summary.get('with_document_category', 0):,}"
    )


def summarize_retrieval_metadata(chunks: list[dict]) -> dict[str, int]:
    """Estimate typed metadata coverage without writing the sidecar DB."""
    unique_sources: dict[str, dict[str, object]] = {}
    for chunk in chunks:
        source_path = str(chunk.get("source_path") or "").strip()
        if not source_path or source_path in unique_sources:
            continue
        derived = derive_source_metadata(source_path, chunk)
        unique_sources[source_path] = {
            "cdrl_code": derived.cdrl_code,
            "incident_id": derived.incident_id,
            "po_number": derived.po_number,
            "contract_number": derived.contract_number,
            "site_token": derived.site_token,
            "is_reference_did": derived.is_reference_did,
            "is_filed_deliverable": derived.is_filed_deliverable,
            "contract_period": derived.contract_period,
            "program_name": derived.program_name,
            "document_type": derived.document_type,
            "document_category": derived.document_category,
        }

    values = list(unique_sources.values())
    return {
        "source_count": len(values),
        "with_cdrl_code": sum(1 for row in values if row["cdrl_code"]),
        "with_incident_id": sum(1 for row in values if row["incident_id"]),
        "with_po_number": sum(1 for row in values if row["po_number"]),
        "with_contract_number": sum(1 for row in values if row["contract_number"]),
        "with_site": sum(1 for row in values if row["site_token"]),
        "reference_dids": sum(1 for row in values if row["is_reference_did"]),
        "filed_deliverables": sum(1 for row in values if row["is_filed_deliverable"]),
        "with_contract_period": sum(1 for row in values if row["contract_period"]),
        "with_program_name": sum(1 for row in values if row["program_name"]),
        "with_document_type": sum(1 for row in values if row["document_type"]),
        "with_document_category": sum(1 for row in values if row["document_category"]),
    }


def run_metadata_backfill(
    export_dir: Path,
    chunks: list[dict],
    manifest: dict,
    config_path: str,
) -> dict[str, object]:
    """Backfill typed retrieval metadata without touching LanceDB chunks/vectors."""
    config = load_config(config_path)
    metadata_db = resolve_retrieval_metadata_db_path(config.paths.lance_db)
    metadata_store = RetrievalMetadataStore(metadata_db)
    summary = metadata_store.upsert_from_chunks(chunks)
    metadata_store.close()

    print(DIVIDER)
    print("  HybridRAG V2 -- Retrieval Metadata Backfill")
    print(DIVIDER)
    print(f"  Source:     {export_dir}")
    _print_metadata_summary(metadata_db, summary)
    report_path = write_import_report(
        export_dir,
        chunks,
        np.zeros((len(chunks), 0), dtype=np.float16),
        manifest,
        mode="metadata_only",
        target_db=metadata_db,
    )
    print(DIVIDER)
    print("  Metadata backfill complete.")
    print(DIVIDER)
    return {
        "mode": "metadata_only",
        "metadata_db": str(metadata_db),
        "metadata_summary": summary,
        "report_path": str(report_path),
    }


def run_dry_run(
    export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    skip_manifest: dict | None,
    config_path: str,
) -> dict[str, object]:
    """Show what would be imported without touching the store."""
    config = load_config(config_path)

    print(DIVIDER)
    print("  HybridRAG V2 -- Import (DRY RUN)")
    print(DIVIDER)
    print_export_summary(export_dir, chunks, vectors, manifest, skip_manifest)
    print()
    print(f"  Target DB:  {config.paths.lance_db}")
    _print_metadata_summary(
        resolve_retrieval_metadata_db_path(config.paths.lance_db),
        summarize_retrieval_metadata(chunks),
    )
    print(f"  Would insert up to {len(chunks):,} chunks (duplicates auto-skipped)")
    report_path = write_import_report(
        export_dir, chunks, vectors, manifest,
        mode="dry_run", target_db=config.paths.lance_db,
    )
    print(DIVIDER)
    print("  Dry run complete. No data was written.")
    print(DIVIDER)
    return {
        "mode": "dry_run",
        "target_db": config.paths.lance_db,
        "planned_chunks": len(chunks),
        "report_path": str(report_path),
    }


def run_import(
    export_dir: Path,
    chunks: list[dict],
    vectors: np.ndarray,
    manifest: dict,
    skip_manifest: dict | None,
    config_path: str,
    create_index: bool,
    index_type: str,
    num_partitions: int | None,
    num_sub_vectors: int | None,
    nprobes: int | None,
    refine_factor: int | None,
    optimize_index: bool,
) -> dict[str, object]:
    """Execute the full import into LanceDB."""
    config = load_config(config_path)

    print(DIVIDER)
    print("  HybridRAG V2 -- Import CorpusForge Export")
    print(DIVIDER)
    print_export_summary(export_dir, chunks, vectors, manifest, skip_manifest)
    print()

    # Enable store-level progress logging so batch inserts print progress
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    # Ingest
    t_start = time.perf_counter()

    store = LanceStore(config.paths.lance_db)
    before_count = store.count()
    print(f"  Inserting {len(chunks):,} chunks in batches of {store.INGEST_BATCH_SIZE:,} ...")
    attempted = len(chunks)
    inserted = store.ingest_chunks(chunks, vectors)
    t_ingest = time.perf_counter() - t_start

    # Integrity check — catches the laptop 10M class of silent truncation
    # at the point of ingest. Does not abort the run; surfaces a loud
    # WARNING so operators see it before the store ships downstream.
    integrity = store.verify_ingest_completeness(
        attempted=attempted,
        before_count=before_count,
        inserted=inserted,
        manifest_count=manifest.get("chunk_count") if isinstance(manifest, dict) else None,
    )
    if not integrity.ok:
        print()
        print("=" * 70, file=sys.stderr)
        print("  [WARN] INGEST INTEGRITY CHECK FAILED", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        for issue in integrity.issues:
            print(f"  - {issue}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print()
    else:
        print(
            f"  [OK] Ingest integrity: attempted={integrity.attempted:,} "
            f"inserted={integrity.inserted:,} duplicates={integrity.duplicates:,} "
            f"net_delta={integrity.net_delta:,}"
        )

    # FTS index
    t_fts_start = time.perf_counter()
    store.create_fts_index()
    t_fts = time.perf_counter() - t_fts_start

    # Optional vector index
    index_result: dict | None = None
    t_idx = 0.0
    if create_index:
        t_idx_start = time.perf_counter()
        index_result = store.create_vector_index(
            num_partitions=num_partitions,
            num_sub_vectors=num_sub_vectors,
            index_type=index_type,
            nprobes=nprobes,
            refine_factor=refine_factor,
            optimize=optimize_index,
        )
        t_idx = time.perf_counter() - t_idx_start

    metadata_db = resolve_retrieval_metadata_db_path(config.paths.lance_db)
    metadata_summary = store.metadata_store.upsert_from_chunks(chunks)

    after_count = store.count()
    vector_index_stats = store.vector_index_stats()
    vector_index_ready = store.vector_index_ready()
    store.close()

    t_total = time.perf_counter() - t_start
    duplicates = len(chunks) - inserted

    # Stats
    print(f"  Target DB:  {config.paths.lance_db}")
    print(f"  Before:     {before_count:,} chunks in store")
    print(f"  Inserted:   {inserted:,} new chunks")
    if duplicates > 0:
        print(f"  Duplicates: {duplicates:,} skipped (already in store)")
    print(f"  After:      {after_count:,} chunks in store")
    _print_metadata_summary(metadata_db, metadata_summary)
    print()
    print(f"  Timing:")
    print(f"    Ingest:       {t_ingest:6.2f}s")
    print(f"    FTS index:    {t_fts:6.2f}s")
    if create_index:
        print(f"    Vector index: {t_idx:6.2f}s")
    print(f"    Total:        {t_total:6.2f}s")
    if inserted > 0 and t_ingest > 0:
        rate = inserted / t_ingest
        print(f"    Rate:         {rate:,.0f} chunks/sec")
    if create_index and index_result:
        print()
        print("  Vector index:")
        created = "yes" if index_result.get("created") else "no"
        print(f"    Created:      {created}")
        print(f"    Type:         {index_result.get('index_type', index_type)}")
        if "rows" in index_result:
            print(f"    Rows:         {index_result['rows']:,}")
        if "num_partitions" in index_result:
            print(f"    Partitions:   {index_result['num_partitions']}")
        if "num_sub_vectors" in index_result:
            print(f"    PQ subvectors:{index_result['num_sub_vectors']}")
        if index_result.get("nprobes") is not None:
            print(f"    nprobes:      {index_result['nprobes']}")
        if index_result.get("refine_factor") is not None:
            print(f"    refine:       {index_result['refine_factor']}")
        print(f"    Optimized:    {'yes' if index_result.get('optimized') else 'no'}")
        stats = index_result.get("index_stats") or {}
        if stats.get("num_indexed_rows") is not None:
            print(f"    Indexed rows: {stats['num_indexed_rows']:,}")
        if stats.get("num_unindexed_rows") is not None:
            print(f"    Unindexed:    {stats['num_unindexed_rows']:,}")
        if index_result.get("index_ready") is not None:
            print(f"    Ready:        {'yes' if index_result['index_ready'] else 'no'}")
        if index_result.get("reason"):
            print(f"    Reason:       {index_result['reason']}")
        if index_result.get("error"):
            print(f"    Error:        {index_result['error']}")
    elif vector_index_stats:
        print()
        print("  Vector index status:")
        if vector_index_stats.get("index_type"):
            print(f"    Type:         {vector_index_stats['index_type']}")
        if vector_index_stats.get("num_indexed_rows") is not None:
            print(f"    Indexed rows: {vector_index_stats['num_indexed_rows']:,}")
        if vector_index_stats.get("num_unindexed_rows") is not None:
            print(f"    Unindexed:    {vector_index_stats['num_unindexed_rows']:,}")
        if vector_index_ready is not None:
            print(f"    Ready:        {'yes' if vector_index_ready else 'no'}")
        if not vector_index_ready:
            print("    Note:         Run optimize/create-index before trusting latency numbers.")

    report_path = write_import_report(
        export_dir, chunks, vectors, manifest,
        mode="import", target_db=config.paths.lance_db,
    )
    print(DIVIDER)
    print("  Import complete.")
    print(DIVIDER)
    return {
        "mode": "import",
        "target_db": config.paths.lance_db,
        "metadata_db": str(metadata_db),
        "before_count": before_count,
        "inserted": inserted,
        "duplicates": duplicates,
        "after_count": after_count,
        "ingest_seconds": round(t_ingest, 3),
        "fts_seconds": round(t_fts, 3),
        "total_seconds": round(t_total, 3),
        "vector_index_enabled": create_index,
        "vector_index_result": index_result if index_result else {},
        "vector_index_stats": vector_index_stats if vector_index_stats else {},
        "vector_index_ready": vector_index_ready,
        "ingest_integrity": integrity.to_dict(),
        "metadata_summary": metadata_summary,
        "report_path": str(report_path),
    }


def main() -> None:
    """Parse command-line inputs and run the main import embedengine workflow."""
    parser = argparse.ArgumentParser(
        description="Import CorpusForge export into HybridRAG V2 LanceDB store."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to CorpusForge export directory (contains chunks.jsonl + vectors.npy).",
    )
    # Keep --export-dir as hidden alias for backwards compatibility
    parser.add_argument(
        "--export-dir",
        dest="source",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to V2 config YAML (default: config/config.yaml).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without writing to the store.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Backfill typed retrieval metadata from chunks.jsonl without touching LanceDB rows.",
    )
    parser.add_argument(
        "--create-index",
        action="store_true",
        help="Build LanceDB IVF_PQ vector index after import (recommended for >10K chunks).",
    )
    parser.add_argument(
        "--index-type",
        default="IVF_PQ",
        help="Vector index type to build when --create-index is set (default: IVF_PQ).",
    )
    parser.add_argument(
        "--num-partitions",
        type=int,
        default=None,
        help="Override IVF partition count (default: sqrt(N)).",
    )
    parser.add_argument(
        "--num-sub-vectors",
        type=int,
        default=None,
        help="Override PQ sub-vector count (default: best divisor of vector dim).",
    )
    parser.add_argument(
        "--nprobes",
        type=int,
        default=20,
        help="Default search nprobes to apply after index creation (default: 20).",
    )
    parser.add_argument(
        "--refine-factor",
        type=int,
        default=None,
        help="Optional LanceDB refine factor for indexed search.",
    )
    parser.add_argument(
        "--no-optimize-index",
        action="store_true",
        help="Skip LanceDB compaction/cleanup after building the vector index.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Reject the entire import if ANY chunk fails field validation.",
    )
    parser.add_argument(
        "--exclude-source-glob",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "TEMPORARY (Sprint 6.6 morning fallback): drop any chunk whose "
            "source_path matches GLOB before import. Repeatable. Example: "
            "--exclude-source-glob '*.SAO.zip' --exclude-source-glob '*.RSF.zip'. "
            "Use to filter the CorpusForge archive-defer leak from the Run 5 "
            "non-canonical export until a clean rerun lands. RETIRE this flag "
            "once a clean rerun is verified."
        ),
    )
    args = parser.parse_args()

    if args.metadata_only and args.dry_run:
        parser.error("--metadata-only cannot be combined with --dry-run")
    if args.metadata_only and args.create_index:
        parser.error("--metadata-only cannot be combined with --create-index")

    export_dir = Path(args.source)
    export_dir = resolve_export_dir(export_dir)

    if not export_dir.is_dir():
        print(f"  ERROR: Export directory not found: {export_dir}", file=sys.stderr)
        sys.exit(1)

    # Load export data
    chunks, vectors, manifest, skip_manifest = load_export(export_dir, strict=args.strict)

    # ------------------------------------------------------------------
    # Sprint 6.6 morning fallback: --exclude-source-glob filter.
    # Visible at startup (before any import work) and at end (excluded
    # count is recorded in the manifest section of the import report).
    # ------------------------------------------------------------------
    exclude_globs = list(args.exclude_source_glob or [])
    pre_filter_count = len(chunks)
    if exclude_globs:
        print("=" * 70)
        print("  TEMPORARY IMPORT FILTER ACTIVE (Sprint 6.6 morning fallback)")
        print("=" * 70)
        print("  Excluding chunks whose source_path matches any of:")
        for g in exclude_globs:
            print(f"    - {g}")
        print(
            "  Reason: CorpusForge archive-defer leak in Run 5 export. "
            "Retire this filter once a clean rerun is verified."
        )
        print("=" * 70)
        chunks, vectors, excluded_count = apply_exclude_source_globs(
            chunks, vectors, exclude_globs,
        )
        print(
            f"  Filter result: {excluded_count} chunks excluded, "
            f"{len(chunks)} kept ({pre_filter_count} -> {len(chunks)})."
        )
        print("=" * 70)
        # Mutate the manifest dict so it propagates into any downstream
        # report writer that copies manifest fields verbatim.
        manifest.setdefault("import_filters", {})
        manifest["import_filters"]["exclude_source_globs"] = exclude_globs
        manifest["import_filters"]["pre_filter_chunk_count"] = pre_filter_count
        manifest["import_filters"]["post_filter_chunk_count"] = len(chunks)
        manifest["import_filters"]["excluded_chunk_count"] = excluded_count
        manifest["import_filters"]["filter_reason"] = (
            "Sprint 6.6 morning fallback: CorpusForge archive-defer leak"
        )
        manifest["import_filters"]["retire_when"] = (
            "After clean rerun confirms zero archive-leaked chunks"
        )
    else:
        # Make the absence of a filter equally visible.
        print("  No --exclude-source-glob filter active.")

    if args.metadata_only:
        run_metadata_backfill(export_dir, chunks, manifest, args.config)
    elif args.dry_run:
        run_dry_run(export_dir, chunks, vectors, manifest, skip_manifest, args.config)
    else:
        run_import(
            export_dir, chunks, vectors, manifest, skip_manifest,
            args.config, args.create_index, args.index_type,
            args.num_partitions, args.num_sub_vectors,
            args.nprobes, args.refine_factor, not args.no_optimize_index,
        )


if __name__ == "__main__":
    main()
