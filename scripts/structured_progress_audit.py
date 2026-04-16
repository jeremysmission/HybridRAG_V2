#!/usr/bin/env python3
"""Audit current structured-store and export-package progress.

This script is intentionally lightweight and operator-oriented:
- reports V2 LanceDB/entity/relationship/table counts
- inspects CorpusForge export packages for chunk/enrichment coverage
- highlights immediate next commands for import/eval

Outputs both JSON and Markdown summaries when requested.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ExportAudit:
    """Structured helper object used by the structured progress audit workflow."""
    path: str
    manifest_path: str | None = None
    chunk_count: int = 0
    enriched_chunks: int = 0
    unique_sources: int = 0
    extension_counts: dict[str, int] = field(default_factory=dict)
    top_source_dirs: list[tuple[str, int]] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass
class StoreAudit:
    """Structured helper object used by the structured progress audit workflow."""
    lance_path: str
    lance_tables: list[str] = field(default_factory=list)
    lance_chunk_count: int | str = 0
    vector_index_present: bool | None = None
    entity_path: str = ""
    entity_count: int | str = 0
    table_row_count: int | str = 0
    relationship_count: int | str = 0
    entity_types: dict[str, int] = field(default_factory=dict)
    predicates: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    """Collect command-line options so the script can decide what work to run."""
    parser = argparse.ArgumentParser(description="Audit structured-store and export progress.")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="HybridRAG V2 config path (default: config/config.yaml).",
    )
    parser.add_argument(
        "--export-dir",
        action="append",
        default=[],
        help="CorpusForge export directory to audit. Can be repeated.",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Directory for generated report files (default: results).",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Explicit JSON report path. Defaults to results/structured_progress_audit_<timestamp>.json",
    )
    parser.add_argument(
        "--md-output",
        default="",
        help="Explicit Markdown report path. Defaults to matching JSON path with .md extension.",
    )
    parser.add_argument(
        "--limit-exports",
        type=int,
        default=2,
        help="When no export dir is provided, inspect the newest N export packages (default: 2).",
    )
    return parser.parse_args()


def _load_config(config_path: Path):
    """Load the data needed for the structured progress audit workflow."""
    import sys

    sys.path.insert(0, str(ROOT))
    from src.config.schema import load_config  # noqa: WPS433

    return load_config(config_path)


def _human_bytes(num: int) -> str:
    """Support the structured progress audit workflow by handling the human bytes step."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def _default_export_dirs(limit: int) -> list[Path]:
    """Support the structured progress audit workflow by handling the default export dirs step."""
    base = ROOT.parent / "CorpusForge" / "data" / "output"
    if not base.exists():
        return []

    manifests: list[Path] = sorted(
        base.glob("**/manifest.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:10]

    ranked: list[tuple[int, float, Path]] = []
    for manifest in manifests:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            chunk_count = int(data.get("chunk_count", 0) or 0)
        except Exception:
            chunk_count = 0
        ranked.append((chunk_count, manifest.stat().st_mtime, manifest.parent))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    export_dirs: list[Path] = []
    seen: set[Path] = set()
    for _, _, export_dir in ranked:
        if export_dir in seen:
            continue
        seen.add(export_dir)
        export_dirs.append(export_dir)
        if len(export_dirs) >= limit:
            break
    return export_dirs


def _collect_store(cfg) -> StoreAudit:
    """Support the structured progress audit workflow by handling the collect store step."""
    store = StoreAudit(
        lance_path=str(Path(cfg.paths.lance_db)),
        entity_path=str(Path(cfg.paths.entity_db)),
    )

    try:
        from src.store.lance_store import LanceStore

        lance = LanceStore(store.lance_path)
        try:
            store.lance_chunk_count = lance.count()
        except Exception as exc:
            store.lance_chunk_count = f"error: {exc}"
        try:
            store.vector_index_present = bool(lance.has_vector_index())
        except Exception:
            store.vector_index_present = None
        try:
            tables = list(lance.db.list_tables())
        except Exception:
            try:
                tables = list(lance.db.table_names())
            except Exception:
                tables = []
        store.lance_tables = tables
        lance.close()
    except Exception as exc:
        store.notes.append(f"LanceDB unavailable: {exc}")

    try:
        from src.store.entity_store import EntityStore

        es = EntityStore(store.entity_path)
        store.entity_count = es.count_entities()
        store.table_row_count = es.count_table_rows()
        store.entity_types = es.entity_type_summary()
        es.close()
    except Exception as exc:
        store.notes.append(f"Entity store unavailable: {exc}")

    try:
        from src.store.relationship_store import RelationshipStore

        rs = RelationshipStore(store.entity_path)
        store.relationship_count = rs.count()
        store.predicates = rs.predicate_summary()
        rs.close()
    except Exception as exc:
        store.notes.append(f"Relationship store unavailable: {exc}")

    return store


def _source_dir_key(source_path: str) -> str:
    """Support the structured progress audit workflow by handling the source dir key step."""
    p = Path(source_path)
    parent = p.parent
    parts = parent.parts
    if len(parts) >= 5:
        return str(Path(*parts[:5]))
    return str(parent)


def _collect_export(export_dir: Path) -> ExportAudit:
    """Support the structured progress audit workflow by handling the collect export step."""
    audit = ExportAudit(path=str(export_dir))
    chunks_path = export_dir / "chunks.jsonl"
    manifest_path = export_dir / "manifest.json"
    audit.manifest_path = str(manifest_path) if manifest_path.exists() else None

    if not chunks_path.exists():
        audit.note = "chunks.jsonl missing"
        return audit

    if manifest_path.exists():
        try:
            audit.manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            audit.note = f"manifest unreadable: {exc}"

    ext_counts: Counter[str] = Counter()
    source_dirs: Counter[str] = Counter()
    unique_sources: set[str] = set()
    total = 0
    enriched = 0

    with chunks_path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            total += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            source_path = str(obj.get("source_path") or "")
            if source_path:
                unique_sources.add(source_path)
                ext_counts[Path(source_path).suffix.lower() or "<none>"] += 1
                source_dirs[_source_dir_key(source_path)] += 1
            enriched_text = obj.get("enriched_text")
            if isinstance(enriched_text, str) and enriched_text.strip():
                enriched += 1

    audit.chunk_count = total
    audit.enriched_chunks = enriched
    audit.unique_sources = len(unique_sources)
    audit.extension_counts = dict(ext_counts.most_common())
    audit.top_source_dirs = list(source_dirs.most_common(10))
    return audit


def _format_md(report: dict[str, Any]) -> str:
    """Turn internal values into human-readable text for the operator."""
    store = report["store"]
    exports = report["exports"]
    lines = [
        "# Structured Progress Audit",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Current Store",
        f"- LanceDB path: `{store['lance_path']}`",
        f"- LanceDB chunks: `{store['lance_chunk_count']}`",
        f"- Vector index present: `{store['vector_index_present']}`",
        f"- Entity rows: `{store['entity_count']}`",
        f"- Table rows: `{store['table_row_count']}`",
        f"- Relationship rows: `{store['relationship_count']}`",
        f"- Entity types: `{store['entity_types']}`",
        f"- Predicates: `{store['predicates']}`",
        "",
        "## Export Packages",
    ]
    for exp in exports:
        lines += [
            f"- `{exp['path']}`",
            f"  - chunks: `{exp['chunk_count']}`",
            f"  - enriched chunks: `{exp['enriched_chunks']}`",
            f"  - unique sources: `{exp['unique_sources']}`",
            f"  - extensions: `{exp['extension_counts']}`",
            f"  - top source dirs: `{exp['top_source_dirs']}`",
        ]
    lines += [
        "",
        "## Immediate Commands",
        "```powershell",
        "cd C:\\HybridRAG_V2",
        ".\\.venv\\Scripts\\python.exe scripts\\health_check.py",
        ".\\.venv\\Scripts\\python.exe scripts\\demo_gate.py --config config\\config.sprint8_demo.yaml --json-output results\\demo_gate_latest.json",
        "```",
        "",
        "```powershell",
        "cd C:\\CorpusForge",
        ".\\.venv\\Scripts\\python.exe scripts\\build_document_dedup_index.py --input C:\\Path\\To\\Source",
        ".\\.venv\\Scripts\\python.exe scripts\\run_pipeline.py --input-list <canonical_files.txt>",
        "```",
    ]
    return "\n".join(lines)


def main() -> int:
    """Parse command-line inputs and run the main structured progress audit workflow."""
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    cfg = _load_config(config_path)

    export_dirs = [Path(p).resolve() for p in args.export_dir]
    if not export_dirs:
        export_dirs = _default_export_dirs(args.limit_exports)

    store = _collect_store(cfg)
    exports = [_collect_export(p) for p in export_dirs]

    report = {
        "generated_at": datetime.now().isoformat(),
        "config": {
            "path": str(config_path),
        },
        "store": asdict(store),
        "exports": [asdict(exp) for exp in exports],
    }

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = Path(args.json_output) if args.json_output else output_dir / f"structured_progress_audit_{timestamp}.json"
    if not json_path.is_absolute():
        json_path = ROOT / json_path
    md_path = Path(args.md_output) if args.md_output else json_path.with_suffix(".md")
    if not md_path.is_absolute():
        md_path = ROOT / md_path

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    md_path.write_text(_format_md(report), encoding="utf-8", newline="\n")

    print("# Structured Progress Audit")
    print(f"Store: {store.lance_path}")
    print(f"Entities: {store.entity_count}")
    print(f"Table rows: {store.table_row_count}")
    print(f"Relationships: {store.relationship_count}")
    for exp in exports:
        print(
            f"Export: {exp.path} | chunks={exp.chunk_count} | "
            f"enriched={exp.enriched_chunks} | sources={exp.unique_sources}"
        )
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
