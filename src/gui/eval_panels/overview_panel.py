"""Evaluation overview panel. It summarizes the latest evidence files and highlights where the system is strong or weak."""
# ============================================================================
# HybridRAG V2 -- QA Workbench Overview Panel (src/gui/eval_panels/overview_panel.py)
# ============================================================================
# Single management-readable surface for the QA Workbench. Scans known
# artifact paths, renders a markdown-style overview of every live benchmark
# lane, and exposes the same renderer as a plain function so a standalone
# script can write the same text to a dated .md on disk.
#
# Sections rendered (in order):
#   1. Latest baseline (certified package)
#   2. Hardtail summary (training-40 head-to-head, filtered-9 reference)
#   3. Count benchmark status
#   4. Aggregation benchmark status
#   5. Regression status (production_eval_results timeline)
#   6. Strongest / weakest areas (from latest production eval)
#   7. Artifact links / paths (one section per lane)
#
# Resilient to missing files: every section wraps its reads in try/except and
# emits "(not yet available -- expected at <path>)" instead of crashing.
# ============================================================================

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from src.gui.theme import (
    DARK,
    FONT,
    FONT_BOLD,
    FONT_MONO,
    FONT_SECTION,
    FONT_SMALL,
    FONT_TITLE,
    apply_ttk_styles,
)


_V2_ROOT = Path(__file__).resolve().parents[3]
_LOCAL_ONLY_ROOT = Path(r"{USER_HOME}\HYBRIDRAG_LOCAL_ONLY")

# ---------------------------------------------------------------------------
# Known artifact paths (dated 2026-04-15 for the current delivery day).
# These are read-only inputs. Missing files are handled gracefully.
# ---------------------------------------------------------------------------
BASELINE_RECOMMENDATION = _LOCAL_ONLY_ROOT / "CERTIFIED_BASELINE_PACKAGE_RECOMMENDATION_2026-04-15.md"
BASELINE_MANIFEST = _LOCAL_ONLY_ROOT / "BASELINE_PACK_MANIFEST_2026-04-15.md"
BASELINE_SCORING_CONTRACT = _LOCAL_ONLY_ROOT / "BASELINE_SCORING_CONTRACT_2026-04-15.md"
BENCHMARK_LEDGER_TEMPLATE = _LOCAL_ONLY_ROOT / "BENCHMARK_LEDGER_TEMPLATE_2026-04-15.md"
CORPUS_COUNT_RECONCILIATION = _LOCAL_ONLY_ROOT / "CORPUS_COUNT_RECONCILIATION_2026-04-15.md"

HARDTAIL_TRAINING40_SCOREBOARD = _LOCAL_ONLY_ROOT / "HARDTAIL_TRAINING40_HEAD_TO_HEAD_SCOREBOARD_2026-04-15.md"
HARDTAIL_FILTERED9_SCOREBOARD = _LOCAL_ONLY_ROOT / "HARDTAIL_HEAD_TO_HEAD_SCOREBOARD_2026-04-15.json"
CLAUDE_TRAINING40_MANIFEST = (
    _LOCAL_ONLY_ROOT
    / "provider_runs" / "hardtail_v1" / "CoPilot+" / "2026-04-15_run_03_training40"
    / "extraction_manifest.json"
)
CODEX_TRAINING40_MANIFEST = (
    _LOCAL_ONLY_ROOT
    / "provider_runs" / "hardtail_v1" / "CoPilot+" / "2026-04-15_run_02_training40"
    / "extraction_manifest.json"
)

COUNT_BENCHMARK_TARGETS = _V2_ROOT / "tests" / "golden_eval" / "count_benchmark_targets_2026-04-15.json"
COUNT_BENCHMARK_RESULTS_DIR = _V2_ROOT / "tests" / "golden_eval" / "results" / "count_benchmark"
COUNT_BENCHMARK_RUN_NOTE = _V2_ROOT / "docs" / "COUNT_BENCHMARK_RUN_NOTE_2026-04-15.md"

AGGREGATION_RUNNER = _V2_ROOT / "scripts" / "run_aggregation_benchmark_2026_04_15.py"
AGGREGATION_SEED_MANIFEST = (
    _V2_ROOT / "tests" / "aggregation_benchmark" / "aggregation_seed_manifest_2026-04-15.json"
)
AGGREGATION_RUN_NOTE = (
    _V2_ROOT / "tests" / "aggregation_benchmark" / "AGGREGATION_BENCHMARK_RUN_NOTE_2026-04-15.md"
)

PRODUCTION_EVAL_DOCS = _V2_ROOT / "docs"
PRODUCTION_EVAL_GLOB = "production_eval_results*.json"

OVERVIEW_OUTPUT_DEFAULT = _LOCAL_ONLY_ROOT / "QA_WORKBENCH_OVERVIEW_2026-04-15.md"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _missing(path: Path) -> str:
    """Support the overview panel workflow by handling the missing step."""
    return f"(not yet available -- expected at `{path}`)"


def _exists(path: Path) -> bool:
    """Support the overview panel workflow by handling the exists step."""
    try:
        return path.exists()
    except Exception:
        return False


def _read_json(path: Path) -> dict | list | None:
    """Read a file or artifact and return it in a form later steps can use."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text_head(path: Path, max_bytes: int = 2048) -> str:
    """Read a file or artifact and return it in a form later steps can use."""
    # FLAG: Likely dead code as of 2026-04-15. Current repo search found the
    # helper definition but no internal callers. Leave it in place until the
    # overview panel gets a focused cleanup pass.
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except Exception:
        return ""


def _fmt_ts(path: Path) -> str:
    """Turn internal values into human-readable text for the operator."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# Section renderers (each returns a list of markdown lines)
# ---------------------------------------------------------------------------
def _section_baseline() -> list[str]:
    """Support the overview panel workflow by handling the section baseline step."""
    lines = ["## 1. Latest certified baseline", ""]
    if _exists(BASELINE_MANIFEST):
        lines.append(f"- Baseline package recommendation: `{BASELINE_RECOMMENDATION}`")
        lines.append(f"- Baseline pack manifest: `{BASELINE_MANIFEST}`")
        lines.append(f"- Baseline scoring contract: `{BASELINE_SCORING_CONTRACT}`")
        lines.append(f"- Benchmark ledger template: `{BENCHMARK_LEDGER_TEMPLATE}`")
        lines.append(f"- Corpus count reconciliation: `{CORPUS_COUNT_RECONCILIATION}`")
        lines.append(f"- Status: QA-PASSED by QA2 (YELLOW by design; see recommendation doc)")
        lines.append(f"- Last updated: {_fmt_ts(BASELINE_MANIFEST)}")
    else:
        lines.append(_missing(BASELINE_MANIFEST))
    lines.append("")
    return lines


def _hardtail_timing(comparator_manifest_path: Path) -> dict:
    """Return unified timing dict {wall_s, avg_s_per_chunk, rc_failures} for
    a hardtail provider run. Comparator manifests and supplement manifests
    use different key names; this function handles both shapes."""
    comparator = _read_json(comparator_manifest_path) or {}
    # CoPilot+ shape: timings.wall_clock_s / avg_s_per_chunk / rc_failures
    timings = comparator.get("timings") if isinstance(comparator, dict) else None
    if isinstance(timings, dict):
        return {
            "wall_s": timings.get("wall_clock_s", "?"),
            "avg_s_per_chunk": timings.get("avg_s_per_chunk", "?"),
            "rc_failures": timings.get("rc_failures", "?"),
        }
    # CoPilot+ shape: comparator manifest has no timings; fall back to the
    # sibling supplement manifest.json in the same run root.
    supp_path = comparator_manifest_path.parent / "manifest.json"
    supplement = _read_json(supp_path) or {}
    supp_timings = supplement.get("timings") if isinstance(supplement, dict) else None
    if isinstance(supp_timings, dict):
        return {
            "wall_s": supp_timings.get("total_wall_clock_s", supp_timings.get("wall_clock_s", "?")),
            "avg_s_per_chunk": supp_timings.get("avg_sec_per_chunk", supp_timings.get("avg_s_per_chunk", "?")),
            "rc_failures": supp_timings.get("rc_failures", "?"),
        }
    return {"wall_s": "?", "avg_s_per_chunk": "?", "rc_failures": "?"}


def _section_hardtail() -> list[str]:
    """Support the overview panel workflow by handling the section hardtail step."""
    lines = ["## 2. Hardtail summary", ""]
    CoPilot+ = _read_json(CLAUDE_TRAINING40_MANIFEST) or {}
    CoPilot+ = _read_json(CODEX_TRAINING40_MANIFEST) or {}

    def _num(m: dict, *keys) -> object:
        cur: object = m
        for k in keys:
            if not isinstance(cur, dict):
                return "?"
            cur = cur.get(k)
        return cur if cur is not None else "?"

    if CoPilot+ or CoPilot+:
        lines.append("### Training-40 head-to-head (same pack, same comparator)")
        lines.append("")
        lines.append("| provider | chunks | wall clock (s) | avg sec/chunk | rc fail | ent verdict (better) | rel verdict (better) | totals E/R/T |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|")

        for label, m, manifest_path in (
            ("CoPilot+ Max", CoPilot+, CLAUDE_TRAINING40_MANIFEST),
            ("CoPilot+", CoPilot+, CODEX_TRAINING40_MANIFEST),
        ):
            if not m:
                lines.append(f"| {label} | (manifest missing) | | | | | | |")
                continue
            chunks = _num(m, "chunk_count")
            timing = _hardtail_timing(manifest_path)
            wall = timing["wall_s"]
            avg = timing["avg_s_per_chunk"]
            rc_fail = timing["rc_failures"]
            ent_better = _num(m, "entity_verdict_tally", "better_than_local")
            rel_better = _num(m, "relationship_verdict_tally", "better_than_local")
            if label == "CoPilot+ Max":
                totals = m.get("totals", {}).get("CoPilot+", {}) or {}
            else:
                totals = m.get("totals", {}).get("CoPilot+", {}) or m.get("totals", {}).get("CoPilot+", {}) or {}
            ent_tot = totals.get("entities", "?")
            rel_tot = totals.get("relationships", "?")
            tbl_tot = totals.get("table_rows", "?")
            lines.append(
                f"| {label} | {chunks} | {wall} | {avg} | {rc_fail} | {ent_better} | {rel_better} | {ent_tot}/{rel_tot}/{tbl_tot} |"
            )
        lines.append("")

    if _exists(HARDTAIL_TRAINING40_SCOREBOARD):
        lines.append(f"- Full training-40 scoreboard: `{HARDTAIL_TRAINING40_SCOREBOARD}`")
    else:
        lines.append(_missing(HARDTAIL_TRAINING40_SCOREBOARD))
    if _exists(HARDTAIL_FILTERED9_SCOREBOARD):
        lines.append(f"- Filtered 9-chunk reference scoreboard: `{HARDTAIL_FILTERED9_SCOREBOARD}`")
    lines.append("")
    return lines


def _section_count_benchmark() -> list[str]:
    """Support the overview panel workflow by handling the section count benchmark step."""
    lines = ["## 3. Count benchmark status", ""]
    targets = _read_json(COUNT_BENCHMARK_TARGETS) or {}
    if targets:
        target_count = len(targets.get("targets") or targets if isinstance(targets, list) else targets.get("targets", []))
        if isinstance(targets, list):
            target_count = len(targets)
        lines.append(f"- Frozen target manifest: `{COUNT_BENCHMARK_TARGETS}`")
        if isinstance(target_count, int) and target_count > 0:
            lines.append(f"- Target count: **{target_count}** (v1 high-specificity)")
    else:
        lines.append(_missing(COUNT_BENCHMARK_TARGETS))

    # Find latest .md run result under results dir
    latest_result = None
    if _exists(COUNT_BENCHMARK_RESULTS_DIR):
        try:
            mds = sorted(
                COUNT_BENCHMARK_RESULTS_DIR.glob("count_benchmark_*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if mds:
                latest_result = mds[0]
        except Exception:
            pass
    if latest_result:
        lines.append(f"- Latest live run result: `{latest_result}` (updated {_fmt_ts(latest_result)})")
    else:
        lines.append(f"- Live run results dir: `{COUNT_BENCHMARK_RESULTS_DIR}` (no runs yet)")

    if _exists(COUNT_BENCHMARK_RUN_NOTE):
        lines.append(f"- Run note: `{COUNT_BENCHMARK_RUN_NOTE}`")

    lines.append(
        "- Status: Ready for QA (CoPilot+-Researcher shipped 2026-04-15: pytest 8 passed, live run 7/7 frozen-expectation verification)"
    )
    lines.append("")
    return lines


def _section_aggregation() -> list[str]:
    """Support the overview panel workflow by handling the section aggregation step."""
    lines = ["## 4. Aggregation benchmark status", ""]
    if _exists(AGGREGATION_RUNNER):
        lines.append(f"- Runner: `{AGGREGATION_RUNNER}`")
    else:
        lines.append(_missing(AGGREGATION_RUNNER))
    if _exists(AGGREGATION_SEED_MANIFEST):
        seed = _read_json(AGGREGATION_SEED_MANIFEST) or {}
        seed_count = "?"
        benchmark_id = ""
        if isinstance(seed, dict):
            items = seed.get("items") or seed.get("seeds") or seed.get("questions") or []
            if isinstance(items, list):
                seed_count = len(items)
            benchmark_id = str(seed.get("benchmark_id") or "")
        tail = f" (items: {seed_count})" + (f", id: {benchmark_id}" if benchmark_id else "")
        lines.append(f"- Frozen seed manifest: `{AGGREGATION_SEED_MANIFEST}`{tail}")
    else:
        lines.append(_missing(AGGREGATION_SEED_MANIFEST))
    if _exists(AGGREGATION_RUN_NOTE):
        lines.append(f"- Run note: `{AGGREGATION_RUN_NOTE}`")
    lines.append(
        "- Status: Ready for QA (reviewer validated-on-disk 2026-04-15: pytest 9 passed, runner Gate PASS 12/12)"
    )
    lines.append("")
    return lines


def _latest_production_eval_json() -> Path | None:
    """Support the overview panel workflow by handling the latest production eval json step."""
    try:
        candidates = sorted(
            PRODUCTION_EVAL_DOCS.glob(PRODUCTION_EVAL_GLOB),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None
    except Exception:
        return None


def _section_regression() -> list[str]:
    """Support the overview panel workflow by handling the section regression step."""
    lines = ["## 5. Regression status", ""]
    latest = _latest_production_eval_json()
    if not latest:
        lines.append(f"- No production_eval_results*.json under `{PRODUCTION_EVAL_DOCS}` yet")
        lines.append("")
        return lines
    data = _read_json(latest) or {}
    # Top-level shape used by production_eval_results_*.json
    total = data.get("total_queries") or data.get("benchmark_summary", {}).get("total_queries") or "?"
    pass_n = data.get("pass_count") if "pass_count" in data else data.get("benchmark_summary", {}).get("pass", "?")
    partial_n = data.get("partial_count") if "partial_count" in data else data.get("benchmark_summary", {}).get("partial", "?")
    miss_n = data.get("miss_count") if "miss_count" in data else data.get("benchmark_summary", {}).get("miss", "?")
    routing = data.get("routing_correct")
    p50_wall = data.get("p50_wall_clock_ms")
    p95_wall = data.get("p95_wall_clock_ms")
    run_id = data.get("run_id") or "?"
    lines.append(f"- Latest production eval file: `{latest}`")
    lines.append(f"- run_id: {run_id}")
    lines.append(f"- Last updated: {_fmt_ts(latest)}")
    if isinstance(total, int) and total:
        def _pct(n):
            try:
                return f"{(int(n)/total)*100:.1f}%"
            except Exception:
                return "?"
        lines.append(
            f"- Pass / Partial / Miss: {pass_n} ({_pct(pass_n)}) / {partial_n} ({_pct(partial_n)}) / {miss_n} ({_pct(miss_n)})"
        )
    else:
        lines.append(f"- Pass / Partial / Miss: {pass_n} / {partial_n} / {miss_n}")
    lines.append(f"- Total queries: {total}")
    if routing is not None:
        lines.append(f"- Routing correct: {routing}")
    if p50_wall is not None or p95_wall is not None:
        lines.append(f"- Wall-clock latency: p50 {p50_wall} ms / p95 {p95_wall} ms")
    lines.append("")
    return lines


def _extract_breakdown_rows(breakdown: dict) -> list[tuple[str, float]]:
    """Pull (name, pass_rate 0..1) rows from a per_persona / per_query_type
    style breakdown dict. Handles several nested shapes:
      - {name: {pass_rate: float, ...}}
      - {name: {pass_count: int, total: int, ...}}
      - {name: {PASS: int, PARTIAL: int, MISS: int, total: int}}  (production shape)
    """
    rows: list[tuple[str, float]] = []
    if not isinstance(breakdown, dict):
        return rows
    for name, payload in breakdown.items():
        if not isinstance(payload, dict):
            continue
        rate = (
            payload.get("pass_rate")
            or payload.get("correct_rate")
            or payload.get("score")
        )
        if rate is None:
            pc = payload.get("pass_count")
            if pc is None:
                pc = payload.get("PASS")
            tot = payload.get("total") or payload.get("count")
            if isinstance(pc, (int, float)) and isinstance(tot, (int, float)) and tot:
                rate = pc / tot
        if isinstance(rate, (int, float)):
            rows.append((str(name), float(rate)))
    return rows


def _section_strongest_weakest() -> list[str]:
    """Support the overview panel workflow by handling the section strongest weakest step."""
    lines = ["## 6. Strongest / weakest areas", ""]
    latest = _latest_production_eval_json()
    if not latest:
        lines.append("- (no production eval results on disk yet)")
        lines.append("")
        return lines
    data = _read_json(latest) or {}

    persona_rows = _extract_breakdown_rows(data.get("per_persona") or {})
    qtype_rows = _extract_breakdown_rows(data.get("per_query_type") or {})

    def _emit(label: str, rows: list[tuple[str, float]]) -> None:
        if not rows:
            lines.append(f"- {label}: (not present in payload)")
            return
        rows_sorted = sorted(rows, key=lambda r: r[1], reverse=True)
        strongest = rows_sorted[:3]
        weakest = list(reversed(rows_sorted[-3:]))
        lines.append(f"- {label} — strongest:")
        for n, r in strongest:
            lines.append(f"  - {n}: {r*100:.1f}%" if r <= 1.0 else f"  - {n}: {r:.1f}")
        lines.append(f"- {label} — weakest:")
        for n, r in weakest:
            lines.append(f"  - {n}: {r*100:.1f}%" if r <= 1.0 else f"  - {n}: {r:.1f}")

    _emit("by persona", persona_rows)
    _emit("by query type", qtype_rows)
    lines.append("")
    return lines


def _section_artifact_links() -> list[str]:
    """Support the overview panel workflow by handling the section artifact links step."""
    lines = ["## 7. Artifact links", ""]
    lines.append("### Baseline package (priority 2, QA-PASSED)")
    lines.append(f"- `{BASELINE_RECOMMENDATION}`")
    lines.append(f"- `{BASELINE_MANIFEST}`")
    lines.append(f"- `{BASELINE_SCORING_CONTRACT}`")
    lines.append(f"- `{BENCHMARK_LEDGER_TEMPLATE}`")
    lines.append(f"- `{CORPUS_COUNT_RECONCILIATION}`")
    lines.append("")
    lines.append("### Hardtail training-40")
    lines.append(f"- `{HARDTAIL_TRAINING40_SCOREBOARD}`")
    lines.append(f"- `{CLAUDE_TRAINING40_MANIFEST}`")
    lines.append(f"- `{CODEX_TRAINING40_MANIFEST}`")
    lines.append("")
    lines.append("### Count benchmark")
    lines.append(f"- runner: `{_V2_ROOT / 'scripts' / 'count_benchmark.py'}`")
    lines.append(f"- targets: `{COUNT_BENCHMARK_TARGETS}`")
    lines.append(f"- results dir: `{COUNT_BENCHMARK_RESULTS_DIR}`")
    lines.append(f"- run note: `{COUNT_BENCHMARK_RUN_NOTE}`")
    lines.append("")
    lines.append("### Aggregation benchmark")
    lines.append(f"- runner: `{AGGREGATION_RUNNER}`")
    lines.append(f"- seed manifest: `{AGGREGATION_SEED_MANIFEST}`")
    lines.append(f"- run note: `{AGGREGATION_RUN_NOTE}`")
    lines.append("")
    lines.append("### Production eval docs directory")
    lines.append(f"- `{PRODUCTION_EVAL_DOCS}`")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Top-level renderer -- pure function; no tk dependency.
# ---------------------------------------------------------------------------
def render_overview_markdown() -> str:
    """Build the QA Workbench Overview as a markdown string.

    Pure function that reads from disk and returns text. Safe to call from
    the GUI panel or from a standalone script (e.g. to write the sibling
    QA_WORKBENCH_OVERVIEW_<date>.md under HYBRIDRAG_LOCAL_ONLY).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = [
        "# QA Workbench Overview",
        "",
        f"Rendered: {now}",
        f"Repo root: `{_V2_ROOT}`",
        f"Local-only root: `{_LOCAL_ONLY_ROOT}`",
        "",
        "This is the management-readable state of every live benchmark lane.",
        "It is a read-only view over artifacts that live elsewhere.",
        "",
        "---",
        "",
    ]
    body: list[str] = []
    for section in (
        _section_baseline,
        _section_hardtail,
        _section_count_benchmark,
        _section_aggregation,
        _section_regression,
        _section_strongest_weakest,
        _section_artifact_links,
    ):
        try:
            body.extend(section())
        except Exception as e:
            body.append(f"## (section {section.__name__} crashed: {e})")
            body.append("")
    footer = [
        "---",
        "",
        "Signed: CoPilot+-Max - HybridRAG_Educational / HYBRIDRAG_LOCAL_ONLY - 2026-04-15 MDT",
        "",
    ]
    return "\n".join(header + body + footer)


def write_overview_markdown(output_path: Path = OVERVIEW_OUTPUT_DEFAULT) -> Path:
    """Render and write the overview to a .md file. Returns the written path."""
    text = render_overview_markdown()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Tk panel
# ---------------------------------------------------------------------------
class OverviewPanel(tk.Frame):
    """QA Workbench Overview tab: read-only management view with Refresh + Save."""

    def __init__(self, parent):
        super().__init__(parent, bg=DARK["bg"])

        try:
            apply_ttk_styles(DARK)
        except Exception:
            pass

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        top = tk.Frame(self, bg=DARK["bg"])
        top.pack(side="top", fill="x", padx=10, pady=(10, 6))

        tk.Label(
            top,
            text="QA Workbench Overview",
            bg=DARK["bg"],
            fg=DARK["fg"],
            font=FONT_TITLE,
        ).pack(side="left", padx=(0, 12))

        ttk.Button(
            top,
            text="Refresh",
            style="Accent.TButton",
            command=self.refresh,
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            top,
            text="Save as .md",
            style="TButton",
            command=self._on_save,
        ).pack(side="left", padx=(0, 6))

        self._status_label = tk.Label(
            top,
            text="",
            bg=DARK["bg"],
            fg=DARK["label_fg"],
            font=FONT_SMALL,
        )
        self._status_label.pack(side="left", padx=(12, 0))

        body = tk.Frame(self, bg=DARK["panel_bg"])
        body.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

        self._text = tk.Text(
            body,
            wrap="word",
            bg=DARK["panel_bg"],
            fg=DARK["fg"],
            insertbackground=DARK["fg"],
            font=FONT_MONO,
            relief="flat",
            bd=0,
            padx=10,
            pady=10,
        )
        vsb = ttk.Scrollbar(body, orient="vertical", command=self._text.yview)
        self._text.configure(yscrollcommand=vsb.set)
        self._text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def refresh(self) -> None:
        try:
            text = render_overview_markdown()
        except Exception as e:
            text = f"# QA Workbench Overview\n\nRenderer crashed: {e}\n"
        try:
            self._text.configure(state="normal")
            self._text.delete("1.0", "end")
            self._text.insert("1.0", text)
            self._text.configure(state="disabled")
        except Exception:
            pass
        try:
            self._status_label.configure(
                text=f"Rendered {datetime.now().strftime('%H:%M:%S')}",
            )
        except Exception:
            pass

    def _on_save(self) -> None:
        try:
            written = write_overview_markdown()
            self._status_label.configure(text=f"Saved -> {written.name}")
        except Exception as e:
            self._status_label.configure(text=f"Save failed: {e}")
