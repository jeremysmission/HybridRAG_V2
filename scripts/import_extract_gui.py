"""
GUI progress panel for V2 walk-away import + extraction pipeline.

Replaces the terminal-only RUN_IMPORT_AND_EXTRACT.bat experience with a
Tkinter window showing live progress. Operator can start, watch (or walk
away), and come back to a DONE/FAILED summary.

Pipeline phases:  IMPORT → TIER 1 REGEX → TIER 2 GLINER → DONE / FAILED

Uses direct Python calls (not subprocess) for real-time progress callbacks.
Follows the proven CorpusForge PipelineRunner + safe_after pattern.
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V2_ROOT))

from src.gui.theme import (
    DARK, FONT, FONT_BOLD, FONT_MONO, FONT_TITLE, FONT_SECTION,
    apply_ttk_styles, current_theme,
)

logger = logging.getLogger(__name__)

# Thread-safe queue for GUI updates from the pipeline thread
_ui_queue: queue.Queue = queue.Queue()


def _safe_after(widget: tk.Misc, ms: int, fn, *args):
    """Schedule fn on the main thread via queue (thread-safe)."""
    if threading.current_thread() is not threading.main_thread():
        if args:
            _ui_queue.put(lambda: fn(*args))
        else:
            _ui_queue.put(fn)
        return None
    try:
        return widget.after(ms, fn, *args)
    except (RuntimeError, tk.TclError):
        return None


def _drain_ui_queue():
    """Drain pending callbacks on the main thread."""
    while True:
        try:
            fn = _ui_queue.get_nowait()
        except queue.Empty:
            break
        try:
            fn()
        except Exception:
            pass


def _format_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:d}h {m:02d}m {s:02d}s"
    if m > 0:
        return f"{m:d}m {s:02d}s"
    return f"{s:d}s"


def _format_count(n: int) -> str:
    return f"{n:,}"


def _get_gpu_info() -> str:
    """Return GPU device name + VRAM or 'CPU only'."""
    try:
        import torch
        if torch.cuda.is_available():
            lines = []
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i)
                free, total = torch.cuda.mem_get_info(i)
                lines.append(f"GPU {i}: {name} ({free / 1e9:.1f} / {total / 1e9:.1f} GB)")
            return " | ".join(lines)
        return "CPU only (CUDA not available)"
    except ImportError:
        return "CPU only (torch not installed)"


# ============================================================================
# Pipeline Runner — background thread
# ============================================================================

class ImportExtractRunner:
    """Runs the import + extraction pipeline in a background thread."""

    def __init__(self, gui: "ImportExtractGUI"):
        self.gui = gui
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, source: str, max_tier: int, config_path: str, skip_import: bool):
        if self.is_alive:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(source, max_tier, config_path, skip_import),
            name="V2-ImportExtract",
            daemon=True,
        )
        self._thread.start()

    def request_stop(self):
        self._stop_event.set()

    def _log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        _safe_after(self.gui.root, 0, self.gui.append_log, f"[{timestamp}] {msg}", level)

    def _set_phase(self, phase: str):
        _safe_after(self.gui.root, 0, self.gui.set_phase, phase)

    def _set_progress(self, current: int, total: int):
        _safe_after(self.gui.root, 0, self.gui.set_progress, current, total)

    def _set_stat(self, key: str, value):
        _safe_after(self.gui.root, 0, self.gui.set_stat, key, value)

    def _run(self, source: str, max_tier: int, config_path: str, skip_import: bool):
        results = {}
        t_start = time.perf_counter()

        try:
            self._set_phase("INITIALIZING")
            self._log("Loading configuration...")

            from src.config.schema import load_config
            config = load_config(config_path)

            source_path = Path(source).resolve()
            self._set_stat("source_path", str(source_path))

            if not skip_import:
                # ---- IMPORT PHASE ----
                if self._stop_event.is_set():
                    self._finish_stopped(results, t_start)
                    return

                self._set_phase("IMPORT")
                self._log(f"Starting import from {source_path}")

                from scripts.import_embedengine import load_export, resolve_export_dir
                from src.store.lance_store import LanceStore

                export_dir = resolve_export_dir(source_path)
                if not export_dir.is_dir():
                    self._finish_failed(f"Export directory not found: {export_dir}", results, t_start)
                    return

                self._log("Loading export files (chunks.jsonl + vectors.npy)...")
                chunks, vectors, manifest, skip_manifest = load_export(export_dir)

                chunk_count = len(chunks)
                self._set_stat("chunks_total", chunk_count)
                self._log(f"Loaded {chunk_count:,} chunks, {vectors.shape[1]}d vectors")

                if manifest:
                    model = manifest.get("embedding_model", "unknown")
                    self._log(f"Embedding model: {model}")

                # Ingest with batch progress
                store = LanceStore(config.paths.lance_db)
                before_count = store.count()
                self._log(f"LanceDB before: {before_count:,} chunks")

                batch_sz = store.INGEST_BATCH_SIZE
                total = len(chunks)
                inserted_total = 0

                import numpy as np

                # Load existing IDs for dedup
                existing_ids: set[str] = set()
                if store._table is not None:
                    try:
                        scanner = store._table.to_lance().scanner(
                            columns=["chunk_id"], batch_size=8192,
                        )
                        for batch in scanner.to_batches():
                            existing_ids.update(batch.column("chunk_id").to_pylist())
                    except Exception:
                        try:
                            existing = (
                                store._table.search()
                                .select(["chunk_id"])
                                .limit(store._table.count_rows())
                                .to_list()
                            )
                            existing_ids = {r["chunk_id"] for r in existing}
                        except Exception:
                            pass

                self._log(f"Ingesting {total:,} chunks in batches of {batch_sz:,}...")

                for start in range(0, total, batch_sz):
                    if self._stop_event.is_set():
                        self._log(f"Stop requested. Ingested {inserted_total:,} chunks so far.")
                        store.close()
                        self._finish_stopped(results, t_start)
                        return

                    end = min(start + batch_sz, total)
                    batch_chunks = chunks[start:end]
                    batch_vecs = vectors[start:end].astype(np.float32)

                    records = []
                    for i, chunk in enumerate(batch_chunks):
                        cid = chunk["chunk_id"]
                        if cid in existing_ids:
                            continue
                        records.append({
                            "chunk_id": cid,
                            "text": chunk["text"],
                            "enriched_text": chunk.get("enriched_text") or "",
                            "vector": batch_vecs[i].tolist(),
                            "source_path": chunk["source_path"],
                            "chunk_index": chunk.get("chunk_index", 0),
                            "parse_quality": chunk.get("parse_quality", 1.0),
                        })

                    if records:
                        if store._table is None:
                            store._table = store.db.create_table(store.TABLE_NAME, data=records)
                        else:
                            store._table.add(records)
                        inserted_total += len(records)

                    self._set_progress(end, total)
                    self._set_stat("chunks_processed", end)
                    self._log(f"Ingested {end:,} / {total:,} ({inserted_total:,} new)")

                # FTS index
                self._log("Building FTS index...")
                store.create_fts_index()

                # Vector index
                self._log("Building vector index (IVF_PQ)...")
                store.create_vector_index()

                after_count = store.count()
                store.close()

                results["import"] = {
                    "status": "PASS",
                    "before": before_count,
                    "inserted": inserted_total,
                    "duplicates": total - inserted_total,
                    "after": after_count,
                }
                self._log(f"Import complete: {inserted_total:,} new, {total - inserted_total:,} dupes, {after_count:,} total")

            # ---- TIER 1 REGEX EXTRACTION ----
            if self._stop_event.is_set():
                self._finish_stopped(results, t_start)
                return

            self._set_phase("TIER 1 REGEX")
            self._set_progress(0, 0)
            self._log("Starting Tier 1 regex extraction...")

            from src.store.lance_store import LanceStore as LS2
            from src.store.entity_store import EntityStore, Entity
            from src.store.relationship_store import RelationshipStore
            from src.extraction.entity_extractor import (
                RegexPreExtractor, EventBlockParser, RegexRelationshipExtractor,
            )
            from collections import Counter

            store = LS2(str(V2_ROOT / config.paths.lance_db))
            entity_store = EntityStore(str(V2_ROOT / config.paths.entity_db))
            rel_store = RelationshipStore(
                str(V2_ROOT / config.paths.entity_db).replace(
                    "entities.sqlite3", "relationships.sqlite3"
                )
            )

            chunk_count = store.count()
            self._set_stat("chunks_total", chunk_count)
            self._log(f"Store has {chunk_count:,} chunks")

            # Load chunks
            from scripts.tiered_extract import load_chunks
            all_chunks = load_chunks(store)
            total_chunks = len(all_chunks)
            self._log(f"Loaded {total_chunks:,} chunks for extraction")

            # Tier 1 extraction with progress
            extractor = RegexPreExtractor(part_patterns=config.extraction.part_patterns)
            event_parser = EventBlockParser(part_patterns=config.extraction.part_patterns)
            rel_extractor = RegexRelationshipExtractor()

            all_entities: list = []
            all_rels: list = []
            seen_entities: set = set()
            seen_rels: set = set()

            t1_start = time.perf_counter()
            progress_interval = max(1, total_chunks // 100)

            for idx, chunk in enumerate(all_chunks):
                if self._stop_event.is_set():
                    self._log(f"Stop requested at chunk {idx:,} / {total_chunks:,}")
                    break

                text = chunk["text"]
                cid = chunk["chunk_id"]
                src = chunk["source_path"]

                entities = extractor.extract(text=text, chunk_id=cid, source_path=src)
                block_entities, block_rels = event_parser.parse(text=text, chunk_id=cid, source_path=src)
                co_rels = rel_extractor.extract(text=text, chunk_id=cid, source_path=src)

                for e in entities + block_entities:
                    key = (e.chunk_id, e.entity_type, e.text)
                    if key not in seen_entities:
                        seen_entities.add(key)
                        all_entities.append(e)

                for r in block_rels + co_rels:
                    key = (r.subject_text, r.predicate, r.object_text, r.chunk_id)
                    if key not in seen_rels:
                        seen_rels.add(key)
                        all_rels.append(r)

                if (idx + 1) % progress_interval == 0 or idx == total_chunks - 1:
                    self._set_progress(idx + 1, total_chunks)
                    self._set_stat("chunks_processed", idx + 1)
                    self._set_stat("tier1_entities", len(all_entities))

            t1_elapsed = time.perf_counter() - t1_start
            t1_types = Counter(e.entity_type for e in all_entities)
            self._log(f"Tier 1: {len(all_entities):,} entities, {len(all_rels):,} rels ({t1_elapsed:.1f}s)")
            self._log(f"  Types: {dict(t1_types)}")

            # Store Tier 1 results
            if all_entities and not self._stop_event.is_set():
                inserted_e = entity_store.insert_entities(all_entities)
                self._log(f"  Stored {inserted_e:,} entities")
            if all_rels and not self._stop_event.is_set():
                inserted_r = rel_store.insert_relationships(all_rels)
                self._log(f"  Stored {inserted_r:,} relationships")

            results["tier1"] = {
                "status": "PASS" if not self._stop_event.is_set() else "STOPPED",
                "entities": len(all_entities),
                "relationships": len(all_rels),
                "elapsed": round(t1_elapsed, 1),
            }

            # ---- TIER 2 GLINER EXTRACTION ----
            if max_tier >= 2 and not self._stop_event.is_set():
                self._set_phase("TIER 2 GLINER")
                self._set_progress(0, 0)
                self._log("Starting Tier 2 GLiNER extraction...")

                try:
                    from gliner import GLiNER
                except ImportError:
                    self._log("GLiNER not installed — skipping Tier 2")
                    results["tier2"] = {"status": "SKIPPED", "reason": "gliner not installed"}
                    self._finish_done(results, t_start)
                    store.close()
                    rel_store.close()
                    return

                import torch

                device = config.extraction.gliner_device
                if "cuda" in device and not torch.cuda.is_available():
                    self._log("CUDA not available — skipping Tier 2 (CPU too slow)")
                    results["tier2"] = {"status": "SKIPPED", "reason": "CUDA not available"}
                    self._finish_done(results, t_start)
                    store.close()
                    rel_store.close()
                    return

                # Resolve device
                resolved_device = device
                if "cuda" in device:
                    requested_idx = int(device.split(":")[1]) if ":" in device else 0
                    if requested_idx >= torch.cuda.device_count():
                        resolved_device = "cuda:0"
                    gpu_idx = int(resolved_device.split(":")[1]) if ":" in resolved_device else 0
                    name = torch.cuda.get_device_name(gpu_idx)
                    free, total_vram = torch.cuda.mem_get_info(gpu_idx)
                    self._set_stat("gpu_status", f"{name} ({free / 1e9:.1f} / {total_vram / 1e9:.1f} GB)")

                # Filter chunks
                min_chunk_len = config.extraction.gliner_min_chunk_len
                filtered = [c for c in all_chunks if len(c["text"].strip()) >= min_chunk_len
                            and sum(1 for ch in c["text"] if ch.isalpha()) / max(len(c["text"]), 1) >= 0.3]
                self._log(f"Tier 2 filter: {total_chunks:,} → {len(filtered):,} chunks")

                # Load model
                self._log(f"Loading GLiNER model: {config.extraction.gliner_model} on {resolved_device}")
                model = GLiNER.from_pretrained(config.extraction.gliner_model)
                if "cuda" in resolved_device:
                    model = model.to(resolved_device)
                    self._log(f"GLiNER loaded on {resolved_device}")

                labels = ["PERSON", "ORGANIZATION", "SITE", "FAILURE_MODE", "DATE"]
                label_map = {"PERSON": "PERSON", "ORGANIZATION": "ORG", "SITE": "SITE",
                             "FAILURE_MODE": "PART", "DATE": "DATE"}
                t2_entities: list = []
                batch_size = 8
                t2_start = time.perf_counter()

                for i in range(0, len(filtered), batch_size):
                    if self._stop_event.is_set():
                        self._log(f"Stop requested at GLiNER batch {i:,}")
                        break

                    batch = filtered[i:i + batch_size]
                    texts = [c["text"][:512] for c in batch]
                    try:
                        batch_results = model.batch_predict_entities(
                            texts, labels, threshold=config.extraction.min_confidence, flat_ner=True,
                        )
                        for chunk, entities in zip(batch, batch_results):
                            for ent in entities:
                                v2_type = label_map.get(ent["label"], ent["label"])
                                key = (chunk["chunk_id"], v2_type, ent["text"].strip())
                                if key not in seen_entities:
                                    seen_entities.add(key)
                                    t2_entities.append(Entity(
                                        entity_type=v2_type,
                                        text=ent["text"].strip(),
                                        raw_text=ent["text"],
                                        confidence=ent["score"],
                                        chunk_id=chunk["chunk_id"],
                                        source_path=chunk["source_path"],
                                        context="",
                                    ))
                    except Exception as e:
                        self._log(f"GLiNER batch error at {i}: {e}")

                    done = min(i + batch_size, len(filtered))
                    self._set_progress(done, len(filtered))
                    self._set_stat("chunks_processed", done)
                    self._set_stat("tier2_entities", len(t2_entities))

                    if done % 500 == 0:
                        self._log(f"GLiNER: {done:,} / {len(filtered):,}, {len(t2_entities):,} entities")

                t2_elapsed = time.perf_counter() - t2_start

                if t2_entities and not self._stop_event.is_set():
                    inserted_e2 = entity_store.insert_entities(t2_entities)
                    self._log(f"Tier 2: {len(t2_entities):,} entities stored ({t2_elapsed:.1f}s)")

                results["tier2"] = {
                    "status": "PASS" if not self._stop_event.is_set() else "STOPPED",
                    "entities": len(t2_entities),
                    "elapsed": round(t2_elapsed, 1),
                }

            store.close()
            rel_store.close()

            if self._stop_event.is_set():
                self._finish_stopped(results, t_start)
            else:
                self._finish_done(results, t_start)

        except Exception as e:
            logger.exception("Pipeline crashed")
            self._finish_failed(str(e), results, t_start)

    def _finish_done(self, results: dict, t_start: float):
        elapsed = time.perf_counter() - t_start
        self._set_phase("DONE")
        self._set_stat("elapsed", _format_elapsed(elapsed))
        self._log(f"Pipeline COMPLETE — {_format_elapsed(elapsed)} total")
        for step, info in results.items():
            self._log(f"  {step}: {info.get('status', 'OK')}")
        _safe_after(self.gui.root, 0, self.gui.on_pipeline_finished, "PASS", results)

    def _finish_stopped(self, results: dict, t_start: float):
        elapsed = time.perf_counter() - t_start
        self._set_phase("STOPPED")
        self._log(f"Pipeline STOPPED by operator — {_format_elapsed(elapsed)}")
        _safe_after(self.gui.root, 0, self.gui.on_pipeline_finished, "STOPPED", results)

    def _finish_failed(self, error: str, results: dict, t_start: float):
        elapsed = time.perf_counter() - t_start
        self._set_phase("FAILED")
        self._log(f"Pipeline FAILED: {error}")
        _safe_after(self.gui.root, 0, self.gui.on_pipeline_finished, "FAIL", results)


# ============================================================================
# GUI Application
# ============================================================================

class ImportExtractGUI:
    """Tkinter GUI for the V2 import + extraction pipeline."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("HybridRAG V2 — Import + Extraction")
        self.root.geometry("900x720")
        self.root.minsize(750, 600)

        t = current_theme()
        self.root.configure(bg=t["bg"])
        apply_ttk_styles(t)

        self._runner: ImportExtractRunner | None = None
        self._start_time: float | None = None
        self._timer_id = None
        self._chunks_total = 0
        self._chunks_processed = 0

        self._build_ui()

        # GPU info on startup
        gpu_info = _get_gpu_info()
        self._stat_values["gpu_status"].configure(text=gpu_info)
        self.append_log(f"GPU: {gpu_info}", "INFO")
        self.append_log("Ready. Select source folder and click Start.", "INFO")

    def _build_ui(self):
        t = current_theme()
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # ---- Title ----
        tk.Label(main, text="HybridRAG V2 — Import + Extraction",
                 font=FONT_TITLE, bg=t["bg"], fg=t["accent"]).pack(pady=(0, 8))

        # ---- Source Selection ----
        src_frame = ttk.LabelFrame(main, text="Source Export")
        src_frame.pack(fill=tk.X, pady=(0, 6))

        src_inner = ttk.Frame(src_frame)
        src_inner.pack(fill=tk.X, padx=8, pady=6)

        self._source_var = tk.StringVar()
        tk.Label(src_inner, text="Export Folder:", font=FONT, bg=t["panel_bg"],
                 fg=t["label_fg"]).pack(side=tk.LEFT)
        self._source_entry = tk.Entry(
            src_inner, textvariable=self._source_var, font=FONT,
            bg=t["input_bg"], fg=t["input_fg"], insertbackground=t["fg"],
            relief="flat", bd=2,
        )
        self._source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        self._browse_btn = ttk.Button(src_inner, text="Browse...", command=self._on_browse)
        self._browse_btn.pack(side=tk.LEFT)

        # ---- Options Row ----
        opt_frame = ttk.Frame(main)
        opt_frame.pack(fill=tk.X, pady=(0, 6))

        self._tier_var = tk.IntVar(value=2)
        tk.Label(opt_frame, text="Max Tier:", font=FONT, bg=t["bg"],
                 fg=t["label_fg"]).pack(side=tk.LEFT)
        ttk.Combobox(opt_frame, textvariable=self._tier_var, values=[1, 2],
                     state="readonly", width=4).pack(side=tk.LEFT, padx=(4, 12))

        self._skip_import_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="Skip Import (LanceDB already populated)",
                        variable=self._skip_import_var).pack(side=tk.LEFT)

        # Buttons
        self._start_btn = ttk.Button(opt_frame, text="Start", style="Accent.TButton",
                                      command=self._on_start)
        self._start_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self._stop_btn = ttk.Button(opt_frame, text="Stop Safely", style="Tertiary.TButton",
                                     command=self._on_stop, state="disabled")
        self._stop_btn.pack(side=tk.RIGHT)

        # ---- Progress Bar ----
        prog_frame = ttk.Frame(main)
        prog_frame.pack(fill=tk.X, pady=(0, 6))

        self._phase_label = tk.Label(prog_frame, text="IDLE", font=FONT_BOLD,
                                      bg=t["bg"], fg=t["accent"])
        self._phase_label.pack(side=tk.LEFT, padx=(0, 8))

        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(
            prog_frame, variable=self._progress_var, maximum=100,
            mode="determinate", length=400,
        )
        self._progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._progress_text = tk.Label(prog_frame, text="0 / 0", font=FONT,
                                        bg=t["bg"], fg=t["fg"])
        self._progress_text.pack(side=tk.LEFT, padx=(8, 0))

        # ---- Stats Panel ----
        stats_frame = ttk.LabelFrame(main, text="Pipeline Status")
        stats_frame.pack(fill=tk.X, pady=(0, 6))

        self._stat_values: dict[str, tk.Label] = {}

        left = ttk.Frame(stats_frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        right = ttk.Frame(stats_frame)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        left_stats = [
            ("source_path", "Source:"),
            ("chunks_total", "Chunks Total:"),
            ("chunks_processed", "Processed:"),
            ("tier1_entities", "Tier 1 Entities:"),
            ("tier2_entities", "Tier 2 Entities:"),
        ]
        right_stats = [
            ("gpu_status", "GPU:"),
            ("elapsed", "Elapsed:"),
            ("eta", "ETA:"),
            ("rate", "Rate:"),
            ("phase_detail", "Detail:"),
        ]

        for key, label_text in left_stats:
            row = ttk.Frame(left)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=label_text, font=FONT, bg=t["panel_bg"],
                     fg=t["label_fg"], width=16, anchor=tk.W).pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=FONT_BOLD, bg=t["panel_bg"],
                           fg=t["fg"], anchor=tk.W, wraplength=350, justify=tk.LEFT)
            val.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._stat_values[key] = val

        for key, label_text in right_stats:
            row = ttk.Frame(right)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=label_text, font=FONT, bg=t["panel_bg"],
                     fg=t["label_fg"], width=12, anchor=tk.W).pack(side=tk.LEFT)
            val = tk.Label(row, text="--", font=FONT_BOLD, bg=t["panel_bg"],
                           fg=t["fg"], anchor=tk.W, wraplength=350, justify=tk.LEFT)
            val.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._stat_values[key] = val

        # ---- Log Panel ----
        log_frame = ttk.LabelFrame(main, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        log_inner = ttk.Frame(log_frame)
        log_inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._log_text = tk.Text(
            log_inner, font=FONT_MONO, bg=t["input_bg"], fg=t["fg"],
            insertbackground=t["fg"], relief="flat", bd=2,
            wrap=tk.WORD, state="disabled", height=12,
        )
        scrollbar = ttk.Scrollbar(log_inner, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tag colors for log levels
        self._log_text.tag_configure("ERROR", foreground=t["red"])
        self._log_text.tag_configure("WARNING", foreground=t["orange"])
        self._log_text.tag_configure("INFO", foreground=t["fg"])

        # ---- Final Status Bar ----
        self._status_bar = tk.Label(
            main, text="", font=FONT_BOLD, bg=t["bg"], fg=t["fg"],
            anchor=tk.W,
        )
        self._status_bar.pack(fill=tk.X)

    # ---- GUI Callbacks ----

    def _on_browse(self):
        path = filedialog.askdirectory(
            title="Select CorpusForge Export Folder",
            initialdir=str(V2_ROOT / "data"),
        )
        if path:
            self._source_var.set(path)

    def _on_start(self):
        source = self._source_var.get().strip()
        skip_import = self._skip_import_var.get()

        if not skip_import and not source:
            self.append_log("ERROR: Select a source export folder first.", "ERROR")
            return

        if not skip_import:
            source_path = Path(source)
            if not source_path.is_dir():
                self.append_log(f"ERROR: Not a directory: {source}", "ERROR")
                return
            chunks_file = source_path / "chunks.jsonl"
            vectors_file = source_path / "vectors.npy"
            if not chunks_file.exists() or not vectors_file.exists():
                self.append_log("ERROR: Missing chunks.jsonl or vectors.npy in export folder.", "ERROR")
                return

        # Lock UI
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._browse_btn.configure(state="disabled")
        self._status_bar.configure(text="", fg=current_theme()["fg"])

        # Reset stats
        self._chunks_total = 0
        self._chunks_processed = 0
        self._start_time = time.time()
        for key in self._stat_values:
            if key != "gpu_status":
                self._stat_values[key].configure(text="--")

        # Start timer
        self._tick_timer()

        # Start runner
        config_path = str(V2_ROOT / "config" / "config.yaml")
        self._runner = ImportExtractRunner(self)
        self._runner.start(source, self._tier_var.get(), config_path, skip_import)

    def _on_stop(self):
        if self._runner and self._runner.is_alive:
            self.append_log("Stop requested — finishing current batch...", "WARNING")
            self._runner.request_stop()
            self._stop_btn.configure(state="disabled")

    def _tick_timer(self):
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            self._stat_values["elapsed"].configure(text=_format_elapsed(elapsed))

            # ETA calculation
            if self._chunks_total > 0 and self._chunks_processed > 0:
                rate = self._chunks_processed / elapsed
                remaining = self._chunks_total - self._chunks_processed
                if rate > 0 and remaining > 0:
                    eta = remaining / rate
                    self._stat_values["eta"].configure(text=_format_elapsed(eta))
                    self._stat_values["rate"].configure(text=f"{rate:,.0f} chunks/sec")
                elif remaining <= 0:
                    self._stat_values["eta"].configure(text="--")

        self._timer_id = self.root.after(1000, self._tick_timer)

    def _stop_timer(self):
        if self._timer_id is not None:
            try:
                self.root.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    # ---- Thread-safe update methods ----

    def append_log(self, msg: str, level: str = "INFO"):
        self._log_text.configure(state="normal")
        tag = level if level in ("ERROR", "WARNING", "INFO") else "INFO"
        self._log_text.insert(tk.END, msg + "\n", tag)
        self._log_text.see(tk.END)
        self._log_text.configure(state="disabled")

    def set_phase(self, phase: str):
        t = current_theme()
        color_map = {
            "IMPORT": t["accent"],
            "TIER 1 REGEX": t["accent"],
            "TIER 2 GLINER": t["accent"],
            "DONE": t["green"],
            "PASS": t["green"],
            "FAILED": t["red"],
            "STOPPED": t["orange"],
        }
        self._phase_label.configure(
            text=phase,
            fg=color_map.get(phase, t["fg"]),
        )

    def set_progress(self, current: int, total: int):
        if total > 0:
            pct = min(100.0, (current / total) * 100.0)
            self._progress_var.set(pct)
            self._progress_text.configure(text=f"{current:,} / {total:,}")
        else:
            self._progress_var.set(0)
            self._progress_text.configure(text="--")

    def set_stat(self, key: str, value):
        if key == "chunks_total":
            self._chunks_total = int(value)
        if key == "chunks_processed":
            self._chunks_processed = int(value)
        if key in self._stat_values:
            display = str(value)
            if isinstance(value, int):
                display = f"{value:,}"
            self._stat_values[key].configure(text=display)

    def on_pipeline_finished(self, status: str, results: dict):
        self._stop_timer()
        t = current_theme()

        # Unlock UI
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._browse_btn.configure(state="normal")

        # Final elapsed
        if self._start_time:
            elapsed = time.time() - self._start_time
            self._stat_values["elapsed"].configure(text=_format_elapsed(elapsed))
            self._stat_values["eta"].configure(text="Done" if status == "PASS" else status)

        # Status bar
        if status == "PASS":
            self._status_bar.configure(text="PIPELINE COMPLETE — ALL PHASES PASSED", fg=t["green"])
            self.set_phase("DONE")
            self._progress_var.set(100)
        elif status == "STOPPED":
            self._status_bar.configure(text="PIPELINE STOPPED — partial results saved", fg=t["orange"])
        else:
            self._status_bar.configure(text="PIPELINE FAILED — check log for details", fg=t["red"])

        # Summary log
        self.append_log("=" * 50, "INFO")
        self.append_log(f"  FINAL STATUS: {status}", "INFO" if status == "PASS" else "ERROR")
        for step, info in results.items():
            if isinstance(info, dict):
                s = info.get("status", "?")
                detail_parts = []
                if "inserted" in info:
                    detail_parts.append(f"{info['inserted']:,} inserted")
                if "entities" in info:
                    detail_parts.append(f"{info['entities']:,} entities")
                if "relationships" in info:
                    detail_parts.append(f"{info['relationships']:,} rels")
                if "elapsed" in info:
                    detail_parts.append(f"{info['elapsed']}s")
                detail = ", ".join(detail_parts)
                self.append_log(f"  {step}: {s} ({detail})", "INFO")
        self.append_log("=" * 50, "INFO")


def main():
    root = tk.Tk()
    app = ImportExtractGUI(root)

    # Pump queue for thread-safe updates
    def pump():
        _drain_ui_queue()
        root.after(50, pump)
    pump()

    def on_close():
        if app._runner and app._runner.is_alive:
            app._runner.request_stop()
        app._stop_timer()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()


if __name__ == "__main__":
    main()
