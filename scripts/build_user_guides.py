"""
Build printable .docx user guides for the QA Workbench and Eval GUI.

Usage:
    python scripts/build_user_guides.py

Outputs:
    docs/QA_WORKBENCH_USER_GUIDE.docx
    docs/EVAL_GUI_USER_GUIDE.docx
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

V2_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = V2_ROOT / "docs"


def _heading(doc: Document, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)


def _para(doc: Document, text: str, bold: bool = False, italic: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(11)


def _bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(text, style="List Bullet")
    for run in p.runs:
        run.font.size = Pt(11)


def _table_row(table, cells: list[str], bold: bool = False) -> None:
    row = table.add_row()
    for i, text in enumerate(cells):
        cell = row.cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.font.size = Pt(10)
        run.bold = bold


def _add_ragas_section(doc: Document) -> None:
    """Add the comprehensive RAGAS explainer section."""
    _heading(doc, "RAGAS: Industry-Standard RAG Evaluation", level=1)

    _heading(doc, "What is RAGAS?", level=2)
    _para(doc, (
        "RAGAS (Retrieval Augmented Generation Assessment) is the industry-standard "
        "open-source framework for evaluating Retrieval-Augmented Generation systems. "
        "Published as a peer-reviewed research paper (arXiv:2309.15217), RAGAS provides "
        "objective, reproducible metrics that measure both retrieval quality and generation "
        "quality. It is the most widely adopted RAG evaluation framework in production use "
        "as of 2026."
    ))

    _heading(doc, "The Five Core Industry-Standard Metrics", level=2)
    _para(doc, (
        "A complete RAG evaluation covers five core metrics across two dimensions: "
        "retrieval quality (did we find the right information?) and generation quality "
        "(did we produce a good answer from it?)."
    ))

    table = doc.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    for i, header in enumerate(["Metric", "Dimension", "What It Measures", "Score Range", "Target"]):
        cell = table.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.size = Pt(10)

    metrics = [
        ["Context Precision", "Retrieval",
         "Are the most relevant chunks ranked highest in retrieval results? Measures signal-to-noise ratio.",
         "0.0 - 1.0", "0.70+"],
        ["Context Recall", "Retrieval",
         "Did we retrieve all the information needed to answer correctly? Measures coverage completeness.",
         "0.0 - 1.0", "0.75+"],
        ["Faithfulness", "Generation",
         "Are all claims in the generated answer actually supported by the retrieved context? Prevents hallucination.",
         "0.0 - 1.0", "0.80+"],
        ["Answer Relevancy", "Generation",
         "Does the generated answer actually address the question that was asked? Measures topical alignment.",
         "0.0 - 1.0", "0.75+"],
        ["Hallucination Rate", "End-to-End",
         "What proportion of responses contain claims not supported by any retrieved evidence?",
         "0.0 - 1.0", "Below 0.05"],
    ]
    for row_data in metrics:
        _table_row(table, row_data)

    _heading(doc, "LLM-Based vs Non-LLM Metrics", level=2)
    _para(doc, (
        "RAGAS metrics come in two variants. LLM-based metrics use a judge model (such as "
        "GPT-4 or Claude) to evaluate semantic quality -- these require API access and incur cost. "
        "Non-LLM metrics use algorithmic approaches (Levenshtein distance, fuzzy matching via "
        "rapidfuzz) to measure retrieval quality without any external API calls."
    ))
    _para(doc, "Our current implementation uses the Non-LLM variants:", bold=True)
    _bullet(doc, "NonLLMContextRecall -- Measures retrieval coverage using fuzzy string matching between retrieved and reference contexts. No API key needed.")
    _bullet(doc, "NonLLMContextPrecisionWithReference -- Measures retrieval precision using Levenshtein similarity against reference contexts. No API key needed.")
    _para(doc, (
        "These are the correct choice for offline evaluation, air-gapped environments, and "
        "cost-controlled testing. LLM-based Faithfulness and Answer Relevancy require a judge "
        "model API and are a planned future enhancement for connected environments."
    ))

    _heading(doc, "Additional Diagnostic Metrics", level=2)
    _para(doc, "Beyond the core five, production RAG systems commonly track:")
    _bullet(doc, "Precision@K -- Fraction of relevant documents in the top-K retrieved results.")
    _bullet(doc, "Recall@K -- Fraction of all relevant documents captured in the top-K results.")
    _bullet(doc, "Mean Reciprocal Rank (MRR) -- Average position of the first relevant result.")
    _bullet(doc, "NDCG -- Normalized Discounted Cumulative Gain, accounts for both relevance and ranking position.")
    _bullet(doc, "BLEU / ROUGE / chrF -- Traditional text-overlap metrics for generation quality.")

    _heading(doc, "How Our System Maps to Industry Standards", level=2)
    table2 = doc.add_table(rows=1, cols=4)
    table2.style = "Light Grid Accent 1"
    for i, header in enumerate(["Industry Metric", "Our Implementation", "Status", "Notes"]):
        cell = table2.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(header)
        run.bold = True
        run.font.size = Pt(10)

    mapping = [
        ["Context Precision", "NonLLMContextPrecisionWithReference", "ACTIVE",
         "Uses rapidfuzz Levenshtein similarity. Runs offline, no API needed."],
        ["Context Recall", "NonLLMContextRecall", "ACTIVE",
         "Fuzzy match between retrieved and reference contexts. Runs offline."],
        ["Faithfulness", "Planned (LLM judge required)", "FUTURE",
         "Requires external API (GPT-4/Claude). Measures claim-level grounding."],
        ["Answer Relevancy", "Planned (LLM judge required)", "FUTURE",
         "Requires external API. Measures question-answer alignment."],
        ["Hallucination Rate", "Derived from Faithfulness", "FUTURE",
         "Computed as 1.0 - Faithfulness when the judge metric is active."],
        ["Precision@K / Recall@K", "Production eval scorer", "ACTIVE",
         "Tracked in the 400-query baseline (PASS/PARTIAL/MISS verdicts)."],
        ["Per-query latency", "Production eval runner", "ACTIVE",
         "p50/p95 wall-clock, router, embed, retrieval timings per query."],
    ]
    for row_data in mapping:
        _table_row(table2, row_data)

    # Tuning knobs reference
    doc.add_page_break()
    _heading(doc, "Tuning Knobs Reference: Retrieval and Generation Parameters", level=1)
    _para(doc, (
        "These are the parameters available for tuning RAG system quality. Each knob "
        "is explained in plain language first, then with technical detail."
    ))

    _heading(doc, "Retrieval-Side Parameters (Finding the Right Information)", level=2)

    _heading(doc, "top_k (Retrieval Depth)", level=3)
    _para(doc, "Plain language: How many document chunks to pull back from the index for each question. Like asking a librarian to bring you their top 5 vs top 20 most relevant books.", italic=True)
    _para(doc, "Technical: Number of nearest-neighbor vectors returned by the embedding search. Higher values increase recall (fewer misses) but decrease precision (more noise). Default: 5. Range: 1-50. Current caveat: top_k is shadowed by TOP_K=5 in the production eval path.")

    _heading(doc, "candidate_pool (Search Width)", level=3)
    _para(doc, "Plain language: How many candidates the system considers before picking the final top_k. Like screening 100 resumes before interviewing 5 people.", italic=True)
    _para(doc, "Technical: Pre-filter pool size before final ranking. Larger pools catch more edge-case matches but cost more compute. Typical: 50-200. Wired in config.yaml as retrieval.candidate_pool.")

    _heading(doc, "nprobes (Index Search Thoroughness)", level=3)
    _para(doc, "Plain language: How many sections of the index to search. More sections = more thorough but slower, like checking more aisles in a library.", italic=True)
    _para(doc, "Technical: Number of IVF partitions to scan in the LanceDB vector index. Higher nprobes increases recall at the cost of latency. Default depends on index size. Set via HYBRIDRAG_LANCE_NPROBES environment variable.")

    _heading(doc, "refine_factor (Result Refinement)", level=3)
    _para(doc, "Plain language: A multiplier that over-fetches candidates then re-scores them for better accuracy. Like pulling 3x the books and then carefully picking the best ones.", italic=True)
    _para(doc, "Technical: LanceDB refine factor. Fetches refine_factor * nprobes candidates, then re-ranks with full-precision vectors. Higher values improve accuracy at increased cost. Set via HYBRIDRAG_LANCE_REFINE_FACTOR.")

    _heading(doc, "reranker_enabled (Two-Stage Ranking)", level=3)
    _para(doc, "Plain language: After the fast initial search, a more careful model re-reads and re-ranks the results. Like having a senior expert review the librarian's picks.", italic=True)
    _para(doc, "Technical: When enabled, a cross-encoder reranker (FlashRank or similar) rescores the candidate_pool using the full query-document pair, not just embeddings. Significantly improves precision at moderate latency cost. Set in config.yaml as retrieval.reranker_enabled.")

    _heading(doc, "Generation-Side Parameters (Producing the Answer)", level=2)

    _heading(doc, "temperature (Creativity vs Consistency)", level=3)
    _para(doc, "Plain language: How creative or predictable the answer should be. Low = very consistent and factual. High = more varied and creative. For factual QA, keep it low.", italic=True)
    _para(doc, "Technical: Controls the softmax distribution over next-token probabilities. Range: 0.0 (deterministic) to 2.0 (very random). For RAG with factual answers, use 0.0-0.3. Higher values increase hallucination risk.")

    _heading(doc, "top_p (Nucleus Sampling)", level=3)
    _para(doc, "Plain language: Instead of considering all possible next words, only consider the most likely ones that together make up this percentage of probability. Keeps answers focused.", italic=True)
    _para(doc, "Technical: Cumulative probability threshold for token selection. top_p=0.9 means only tokens in the top 90% probability mass are considered. Lower values = more focused output. Range: 0.0-1.0. Often used with temperature.")

    _heading(doc, "top_k (Generation Sampling)", level=3)
    _para(doc, "Plain language: Only consider the K most likely next words at each step. Prevents rare, off-topic word choices. Different from retrieval top_k.", italic=True)
    _para(doc, "Technical: Limits token selection to the K highest-probability candidates. top_k=50 is common. Use with temperature > 0. Not applicable when temperature = 0 (greedy decoding).")

    _heading(doc, "max_tokens (Response Length)", level=3)
    _para(doc, "Plain language: Maximum length of the generated answer. Prevents runaway responses.", italic=True)
    _para(doc, "Technical: Hard cap on generated output tokens. Set based on expected answer length. Too low truncates answers; too high wastes tokens on padding or repetition. Typical: 256-1024 for QA.")

    _heading(doc, "repetition_penalty (Anti-Repetition)", level=3)
    _para(doc, "Plain language: Discourages the model from repeating the same phrases over and over.", italic=True)
    _para(doc, "Technical: Multiplicative penalty applied to tokens already generated. 1.0 = no penalty. 1.1-1.3 = mild discouragement. Higher values may break coherence. Useful for long-form generation.")

    _heading(doc, "context_window (Input Capacity)", level=3)
    _para(doc, "Plain language: How much retrieved text the model can read at once. Bigger window = more context but more expensive.", italic=True)
    _para(doc, "Technical: Maximum input token length for the generation model. Determines how many retrieved chunks can be packed into a single prompt. Models range from 4K to 128K+ tokens. Our Phi-4 local model supports 16K context.")

    _heading(doc, "Interpreting RAGAS Scores", level=2)
    _bullet(doc, "1.0 = Perfect. Every retrieved chunk is relevant, and all relevant chunks are retrieved.")
    _bullet(doc, "0.7 - 0.9 = Good. Production-ready for most use cases.")
    _bullet(doc, "0.5 - 0.7 = Fair. Improvement needed. Check chunk quality, embedding model, or retrieval parameters.")
    _bullet(doc, "Below 0.5 = Poor. Significant retrieval or indexing issues. Investigate corpus coverage and embedding alignment.")
    _para(doc, (
        "When comparing runs, a meaningful improvement is typically 0.05+ on any single metric. "
        "Changes smaller than 0.02 may be noise. Always compare on the same query pack and same "
        "corpus version."
    ))


def _add_qa_workbench_content(doc: Document) -> None:
    """Build the QA Workbench user guide content."""
    # Title page
    title = doc.add_heading("HybridRAG V2 -- QA Workbench User Guide", level=0)
    for run in title.runs:
        run.font.color.rgb = RGBColor(0, 48, 135)
    _para(doc, f"Version: 2026-04-15  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    _para(doc, "This guide covers every tab in the QA Workbench, how to set up and run each test, what results mean, and what to watch for.")
    doc.add_page_break()

    # Quick Start
    _heading(doc, "Quick Start", level=1)
    _para(doc, "Prerequisites:", bold=True)
    _bullet(doc, "Windows 10/11 with NVIDIA GPU (CUDA required)")
    _bullet(doc, "HybridRAG V2 repo cloned with .venv installed (run INSTALL_EVAL_GUI.bat if needed)")
    _bullet(doc, "LanceDB index built and populated (data/ directory)")
    _para(doc, "Launch:", bold=True)
    _bullet(doc, 'Double-click start_qa_workbench.bat, or from terminal: cd /d C:\\HybridRAG_V2 && start_qa_workbench.bat')
    _bullet(doc, "The window opens with 7 tabs: Overview, Baseline, Aggregation, Count, RAGAS, Regression, History/Ledger")
    _bullet(doc, "Use the vertical scrollbar on the right to scroll if the window is small")
    _bullet(doc, 'Proxy/network: The launcher auto-configures proxy settings. Behind a corporate proxy, set HTTPS_PROXY in your shell before launching.')

    # Tab: Overview
    _heading(doc, "Tab 1: Overview", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "A read-only management dashboard showing the current state of all measurement lanes at a glance.")
    _para(doc, "What it shows:", bold=True)
    _bullet(doc, "Certified baseline status and scores")
    _bullet(doc, "Hardtail head-to-head comparison (provider speed and quality)")
    _bullet(doc, "Count benchmark results (corpus coverage)")
    _bullet(doc, "Aggregation benchmark results (cross-document accuracy)")
    _bullet(doc, "Production eval strongest/weakest persona and query type")
    _bullet(doc, "Regression timeline")
    _para(doc, "No setup needed:", italic=True)
    _para(doc, "This tab reads from existing result files. If a file is missing, the panel shows '(not yet available)' gracefully.")

    # Tab: Baseline
    _heading(doc, "Tab 2: Baseline (Production Eval)", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Run the full 400-query production evaluation against the live index. This is the primary quality measurement.")
    _heading(doc, "Setup", level=3)
    _bullet(doc, "Query Pack: Default is production_queries_400_2026-04-12.json (400 curated queries across 3 personas)")
    _bullet(doc, "Config: Default is config.yaml. Change only if testing a specific configuration variant.")
    _bullet(doc, "GPU: Select GPU index (0 or 1). Check nvidia-smi if unsure which is available.")
    _bullet(doc, "Max Queries: Leave blank for full 400. Set to 5-10 for a quick smoke test.")
    _heading(doc, "Running", level=3)
    _bullet(doc, "Click Start. The progress bar advances per query. Live log shows per-query verdicts (green=PASS, orange=PARTIAL, red=MISS).")
    _bullet(doc, "Click Stop at any time to safely halt after the current query. Partial results are saved.")
    _heading(doc, "Interpreting Results", level=3)
    _bullet(doc, "PASS = Retrieved context contains the expected answer material")
    _bullet(doc, "PARTIAL = Some relevant content retrieved but incomplete")
    _bullet(doc, "MISS = Expected content not in retrieved results")
    _bullet(doc, "Scorecard shows pass/partial/miss totals, routing accuracy, and latency percentiles")
    _heading(doc, "What to Watch For", level=3)
    _bullet(doc, "PASS rate below 60% = significant retrieval problem")
    _bullet(doc, "p95 latency above 30s = performance issue (check GPU load)")
    _bullet(doc, "High MISS rate on a specific persona = corpus gap for that query type")
    _para(doc, "Sub-tabs: Results (browse past runs), Compare (diff two runs), History (all runs over time)")

    # Tab: Aggregation
    _heading(doc, "Tab 3: Aggregation", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Tests cross-document aggregation accuracy. Can the system combine information from multiple sources correctly?")
    _heading(doc, "Setup", level=3)
    _bullet(doc, "Manifest: Default is aggregation_seed_manifest_2026-04-15.json (12 items)")
    _bullet(doc, "Answers: Leave blank for self-check mode (fastest). Provide an answers JSON to score against external predictions.")
    _bullet(doc, "Min Pass Rate: Default 1.0 (100% required to pass gate)")
    _heading(doc, "Running", level=3)
    _bullet(doc, "Click Start. Each item is scored and logged (green=PASS, red=FAIL).")
    _bullet(doc, "Click Stop to halt safely between items.")
    _heading(doc, "Interpreting Results", level=3)
    _bullet(doc, "12/12 in self-check = certified baseline is intact")
    _bullet(doc, "Any failure = regression detected. Check the specific item in the log for expected vs actual.")

    # Tab: Count
    _heading(doc, "Tab 4: Count", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Verifies corpus coverage by counting entity mentions, documents, chunks, and rows for known targets.")
    _heading(doc, "Setup", level=3)
    _bullet(doc, "Targets: Default is count_benchmark_targets_2026-04-15.json")
    _bullet(doc, "LanceDB Path: Path to your indexed LanceDB directory")
    _bullet(doc, "Entity DB: Path to the entity SQLite database")
    _bullet(doc, "Modes: raw_mentions, unique_documents, unique_chunks, unique_rows (all on by default)")
    _heading(doc, "Running", level=3)
    _bullet(doc, "Click Start. Each target is counted against the live store.")
    _bullet(doc, "Click Stop to halt safely between targets.")
    _heading(doc, "Interpreting Results", level=3)
    _bullet(doc, "7/7 frozen-expectation match = corpus is complete and dedup is stable")
    _bullet(doc, "Count mismatch = either new data was ingested (expected) or dedup changed (investigate)")

    # Tab: RAGAS
    _heading(doc, "Tab 5: RAGAS", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Industry-standard retrieval quality measurement using the RAGAS framework. Provides objective, reproducible scores for context precision and context recall.")
    _heading(doc, "Setup", level=3)
    _bullet(doc, "Query JSON: Default is the 400-query production pack")
    _bullet(doc, "Limit: Number of queries to evaluate. Leave blank for all eligible. Set to 3-10 for quick tests.")
    _bullet(doc, "Analysis Only: Check this to see readiness stats without running metrics (fast, no GPU needed)")
    _heading(doc, "Running", level=3)
    _bullet(doc, "Click Start. Analysis-only completes in seconds. Full execution evaluates each query's retrieval quality.")
    _bullet(doc, "Click Stop to halt safely between queries.")
    _heading(doc, "Interpreting Results", level=3)
    _bullet(doc, "eligible: X/400 = how many queries have the ground-truth data needed for RAGAS scoring")
    _bullet(doc, "phase2c: X/400 = how many queries have Phase 2C enrichment (reference contexts)")
    _bullet(doc, "nonllm_context_recall mean = average retrieval coverage score (target: 0.75+)")
    _bullet(doc, "nonllm_context_precision mean = average retrieval precision score (target: 0.70+)")
    _bullet(doc, "errors = 0 means clean execution; errors > 0 means some queries had scoring issues")
    _heading(doc, "What to Watch For", level=3)
    _bullet(doc, "Low eligible count = query pack needs more ground-truth annotation")
    _bullet(doc, "Context recall below 0.5 = retrieval is missing key information; check chunk size, embedding model, or nprobes")
    _bullet(doc, "Context precision below 0.5 = retrieval is returning too much noise; check candidate_pool or reranker settings")

    # Tab: Regression
    _heading(doc, "Tab 6: Regression", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Fast guardrail check. Runs a frozen set of 50 known-good extraction patterns to catch regressions before demo or release.")
    _heading(doc, "Setup", level=3)
    _bullet(doc, "Fixture: Default is fixture_2026_04_15.json (50 cases across 5 entity families)")
    _bullet(doc, "No database or GPU needed. Runs against a deterministic classifier.")
    _heading(doc, "Running", level=3)
    _bullet(doc, "Click Run Regression. Completes in 1-3 seconds.")
    _heading(doc, "Interpreting Results", level=3)
    _bullet(doc, "50/50 PASS = all known patterns still work correctly")
    _bullet(doc, "Any failure = a code change broke an extraction pattern. Check the failure detail for which family and case.")
    _bullet(doc, "Per-family table shows which entity types passed/failed (SITE, PERSON, CONTACT, DATE, ORG)")

    # Tab: History/Ledger
    _heading(doc, "Tab 7: History / Ledger", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Browse all past evaluation runs in a sortable table. Track quality over time.")
    _para(doc, "What it shows:", bold=True)
    _bullet(doc, "Every production eval run with timestamp, pack, config, scores, and latency")
    _bullet(doc, "Sortable columns -- click any header to sort")
    _bullet(doc, "Provenance strip with links to certified baseline artifacts")
    _para(doc, "Tip:", italic=True)
    _para(doc, "After making a retrieval-side code change, the recommended benchmark order is: Regression -> Count -> Aggregation -> Baseline -> append ledger row.")

    # RAGAS deep-dive
    doc.add_page_break()
    _add_ragas_section(doc)

    # Troubleshooting
    doc.add_page_break()
    _heading(doc, "Troubleshooting", level=1)
    _bullet(doc, "Window opens and closes immediately: Run from terminal to see error. Most common: missing .venv or broken Python install. Run INSTALL_EVAL_GUI.bat.")
    _bullet(doc, "CUDA not available: Check nvidia-smi. Ensure CUDA_VISIBLE_DEVICES is set (launcher defaults to 0).")
    _bullet(doc, "Proxy errors on launch: Set HTTPS_PROXY and HTTP_PROXY in your shell before launching. The launcher inherits these.")
    _bullet(doc, "RAGAS blocked: Run the RAGAS installer: powershell -File tools\\install_ragas_proxy_ready_2026-04-15.ps1")
    _bullet(doc, "White text invisible: Update to latest version. TEntry styling was fixed in the 2026-04-15 theme update.")
    _bullet(doc, "Results not appearing in History: Results must be saved as production_eval_results*.json in the docs/ directory.")


def _add_eval_gui_content(doc: Document) -> None:
    """Build the Eval GUI user guide content."""
    title = doc.add_heading("HybridRAG V2 -- Eval GUI User Guide", level=0)
    for run in title.runs:
        run.font.color.rgb = RGBColor(0, 48, 135)
    _para(doc, f"Version: 2026-04-15  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    _para(doc, "This guide covers every tab in the Eval GUI, how to run evaluations, interpret results, and use RAGAS metrics.")
    doc.add_page_break()

    # Quick Start
    _heading(doc, "Quick Start", level=1)
    _para(doc, "Prerequisites:", bold=True)
    _bullet(doc, "Windows 10/11 with NVIDIA GPU (CUDA required)")
    _bullet(doc, "HybridRAG V2 repo with .venv installed")
    _bullet(doc, "LanceDB index built and populated")
    _para(doc, "Launch:", bold=True)
    _bullet(doc, 'Double-click start_eval_gui.bat, or from terminal: cd /d C:\\HybridRAG_V2 && start_eval_gui.bat')
    _bullet(doc, "The window opens with 8 tabs: Overview, Launch, Aggregation, Count, RAGAS, Results, Compare, History")

    # Tab: Overview
    _heading(doc, "Tab 1: Overview", level=1)
    _para(doc, "Read-only dashboard showing all measurement lanes. Same content as the QA Workbench Overview tab. See QA Workbench guide for full details.")

    # Tab: Launch
    _heading(doc, "Tab 2: Launch (Production Eval)", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Run the 400-query production evaluation. This is the operator's primary tool for measuring system quality.")
    _heading(doc, "Setup", level=3)
    _bullet(doc, "Query Pack: Select the query JSON (default: 400-query production pack)")
    _bullet(doc, "Config: Select config YAML (default: config.yaml)")
    _bullet(doc, "Output: Results JSON and Markdown report paths (auto-generated)")
    _bullet(doc, "GPU Index: Which GPU to use (check nvidia-smi)")
    _bullet(doc, "Max Queries: Blank for full run, or a number for smoke test")
    _heading(doc, "Running", level=3)
    _bullet(doc, "Click Start. Progress bar and live log stream results.")
    _bullet(doc, "Click Stop to safely halt after the current query.")
    _bullet(doc, "Save as Defaults to persist your input paths for next launch.")
    _heading(doc, "Interpreting Results", level=3)
    _bullet(doc, "Scorecard fills in as queries complete: PASS/PARTIAL/MISS counts")
    _bullet(doc, "Green log lines = PASS, Orange = PARTIAL, Red = MISS")
    _bullet(doc, "After completion, results JSON is written to docs/")

    # Tab: Aggregation
    _heading(doc, "Tab 3: Aggregation", level=1)
    _para(doc, "Same as QA Workbench. See the QA Workbench guide for detailed setup, running, and interpretation instructions.")

    # Tab: Count
    _heading(doc, "Tab 4: Count", level=1)
    _para(doc, "Same as QA Workbench. See the QA Workbench guide for detailed setup, running, and interpretation instructions.")

    # Tab: RAGAS
    _heading(doc, "Tab 5: RAGAS", level=1)
    _para(doc, "Same as QA Workbench. See the QA Workbench guide for detailed RAGAS setup, running, and interpretation.")

    # Tab: Results
    _heading(doc, "Tab 6: Results", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Browse and filter a completed evaluation run in detail.")
    _heading(doc, "How to Use", level=3)
    _bullet(doc, "Load a results JSON (auto-loads after a Launch run, or browse to pick any past result)")
    _bullet(doc, "Filter by Verdict (PASS/PARTIAL/MISS), Persona, Family, or Query Type")
    _bullet(doc, "Click a query row to see full details: expected vs actual routing, top retrieved chunks, per-stage timing")
    _heading(doc, "What to Watch For", level=3)
    _bullet(doc, "Routing mismatches: expected query type differs from actual routed type")
    _bullet(doc, "High latency outliers: per-query wall clock significantly above p50")
    _bullet(doc, "Empty retrieved chunks: indicates a retrieval failure for that query")

    # Tab: Compare
    _heading(doc, "Tab 7: Compare", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "Diff two evaluation runs side-by-side to see what changed.")
    _heading(doc, "How to Use", level=3)
    _bullet(doc, "Select Run A (before) and Run B (after)")
    _bullet(doc, "Headline shows delta: +/- PASS, PARTIAL, MISS counts")
    _bullet(doc, "Filter: Changed Only, Gains Only, Losses Only, or All")
    _bullet(doc, "Table shows per-query transitions: green for improvements (MISS->PASS), red for regressions (PASS->MISS)")
    _heading(doc, "What to Watch For", level=3)
    _bullet(doc, "Net gains > net losses = improvement confirmed")
    _bullet(doc, "Any PASS->MISS transitions warrant investigation before accepting the change")

    # Tab: History
    _heading(doc, "Tab 8: History", level=1)
    _para(doc, "Purpose:", bold=True)
    _para(doc, "All past evaluation runs in a sortable table. Same as QA Workbench History/Ledger.")
    _para(doc, "Scans docs/ for all production_eval_results*.json files and displays them sorted by timestamp.")

    # RAGAS section
    doc.add_page_break()
    _add_ragas_section(doc)

    # Troubleshooting
    doc.add_page_break()
    _heading(doc, "Troubleshooting", level=1)
    _bullet(doc, "Window opens and closes: Run from terminal. Check for SyntaxError or import failures.")
    _bullet(doc, "CUDA not available: Verify nvidia-smi shows your GPU. Set CUDA_VISIBLE_DEVICES=0 in shell.")
    _bullet(doc, "Proxy errors: Set HTTPS_PROXY before launching. The shared preflight helper inherits your proxy settings.")
    _bullet(doc, "RAGAS not installed: Run tools\\install_ragas_proxy_ready_2026-04-15.ps1")
    _bullet(doc, "Compare shows no changes: Ensure both result JSONs use the same query pack version.")


def main() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # QA Workbench guide
    doc1 = Document()
    style = doc1.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    _add_qa_workbench_content(doc1)
    path1 = DOCS_DIR / "QA_WORKBENCH_USER_GUIDE.docx"
    doc1.save(str(path1))
    print(f"Written: {path1}")

    # Eval GUI guide
    doc2 = Document()
    style2 = doc2.styles["Normal"]
    style2.font.name = "Calibri"
    style2.font.size = Pt(11)
    _add_eval_gui_content(doc2)
    path2 = DOCS_DIR / "EVAL_GUI_USER_GUIDE.docx"
    doc2.save(str(path2))
    print(f"Written: {path2}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
