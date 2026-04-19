"""Query panel. It is the main operator screen for asking questions and viewing answers."""
# ============================================================================
# HybridRAG V2 -- Query Panel (src/gui/panels/query_panel.py)
# ============================================================================
# Main search interface: type a question, get an answer.
# V2 additions over V1:
#   - Query path badge (colored: SEMANTIC/ENTITY/AGGREGATE/TABULAR/COMPLEX)
#   - Graduated confidence indicator (green=HIGH, yellow=PARTIAL, red=NOT_FOUND)
#   - Streaming token display (background thread + safe_after + token queue)
#   - Source citations expandable section
#   - Stop button for cancellation
#   - Uses GUIModel.query() -- not direct pipeline access
# ============================================================================

import json
import tkinter as tk
from tkinter import ttk
import threading
import time
import logging
import queue
from datetime import datetime
from pathlib import Path

from src.gui.theme import current_theme, FONT, FONT_BOLD, FONT_SMALL, FONT_MONO
from src.gui.helpers.safe_after import safe_after

logger = logging.getLogger(__name__)

# Query path badge colors (looked up from theme at render time)
_PATH_COLORS = {
    "SEMANTIC": "accent",
    "ENTITY": "green",
    "AGGREGATE": "orange",
    "TABULAR": "orange",
    "COMPLEX": "red",
}

# Confidence badge colors
_CONFIDENCE_COLORS = {
    "HIGH": "green",
    "PARTIAL": "orange",
    "NOT_FOUND": "red",
}

# Evidence basis classification for aggregation-capable answers
_EVIDENCE_LABELS = {
    "EXACT_COUNT": ("\u2713 Exact Count", "green"),
    "BOUNDED_COUNT": ("\u2248 Bounded Count", "orange"),
    "INFERRED_SCHEDULE": ("\u23F0 Inferred Schedule", "orange"),
    "QUALITATIVE": ("\u2139 Qualitative", "accent"),
}


def _classify_evidence_basis(query: str, answer: str, query_path: str) -> str:
    """Classify the evidence basis of an answer for operator display.

    Returns one of: EXACT_COUNT, BOUNDED_COUNT, INFERRED_SCHEDULE, QUALITATIVE.
    """
    q = query.lower()
    a = answer.lower()

    # Check for aggregation/count queries
    is_count_query = any(w in q for w in (
        "how many", "count", "total", "number of", "list all",
        "which sites", "which cdrl", "what deliverables",
    ))

    if is_count_query and query_path == "AGGREGATE":
        # Check if answer contains specific numbers
        import re
        has_number = bool(re.search(r"\b\d+\b", a))
        has_exact_language = any(w in a for w in (
            "found", "total of", "identified", "counted", "records show",
        ))
        if has_number and has_exact_language:
            return "EXACT_COUNT"
        elif has_number:
            return "BOUNDED_COUNT"

    # Check for schedule/cadence queries
    is_schedule_query = any(w in q for w in (
        "when is", "due date", "schedule", "deadline", "next",
        "recurring", "cadence", "monthly", "quarterly",
    ))
    if is_schedule_query:
        has_inferred = any(w in a for w in (
            "appears to", "likely", "based on", "pattern suggests",
            "recurring", "typically",
        ))
        if has_inferred:
            return "INFERRED_SCHEDULE"

    return "QUALITATIVE"


class QueryPanel(tk.LabelFrame):
    """Query input and answer display panel.

    Shows question entry, Ask/Stop buttons, streaming answer area,
    query path badge, confidence indicator, and expandable sources.
    """

    def __init__(self, parent, model):
        """Create the query panel.

        Args:
            parent: Parent tk widget.
            model: GUIModel instance for dispatching queries.
        """
        t = current_theme()
        super().__init__(parent, text="Query", padx=16, pady=16,
                         bg=t["panel_bg"], fg=t["accent"],
                         font=FONT_BOLD)
        self._model = model
        self._streaming = False
        self._stream_start = 0.0
        self._elapsed_timer_id = None
        self._token_queue = queue.Queue()
        self._token_pump_id = None

        self._build_widgets(t)

        # Enable Ask button if pipeline is available
        self.after(200, self._check_ready)

    def _build_widgets(self, t):
        """Build all child widgets with theme colors."""

        # -- Row 0: Badge row (query path + confidence) --
        badge_row = tk.Frame(self, bg=t["panel_bg"])
        badge_row.pack(fill=tk.X, pady=(0, 8))

        self._path_badge = tk.Label(
            badge_row, text="", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["gray"], padx=8, pady=2,
        )
        self._path_badge.pack(side=tk.LEFT)

        self._confidence_badge = tk.Label(
            badge_row, text="", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["gray"], padx=8, pady=2,
        )
        self._confidence_badge.pack(side=tk.LEFT, padx=(8, 0))

        self._evidence_badge = tk.Label(
            badge_row, text="", font=FONT_BOLD,
            bg=t["panel_bg"], fg=t["gray"], padx=8, pady=2,
        )
        self._evidence_badge.pack(side=tk.LEFT, padx=(8, 0))

        self._elapsed_label = tk.Label(
            badge_row, text="", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["gray"],
        )
        self._elapsed_label.pack(side=tk.RIGHT)

        # -- Row 1: Question + Ask + Stop --
        q_label = tk.Label(
            self, text="Question:", bg=t["panel_bg"],
            fg=t["fg"], font=FONT, anchor=tk.W,
        )
        q_label.pack(fill=tk.X, pady=(0, 4))

        row_q = tk.Frame(self, bg=t["panel_bg"])
        row_q.pack(fill=tk.X, pady=(0, 6))

        self.question_entry = tk.Entry(
            row_q, font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=2,
        )
        self.question_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.question_entry.insert(0, "Type your question here...")
        self.question_entry.bind("<FocusIn>", self._on_entry_focus)
        self.question_entry.bind("<Return>", self._on_ask)
        self.question_entry.bind("<Escape>", self._on_stop)

        self.ask_btn = tk.Button(
            row_q, text="Ask", command=self._on_ask, width=10,
            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            font=FONT_BOLD, relief=tk.FLAT, bd=0,
            padx=24, pady=8, state=tk.DISABLED,
            activebackground=t["accent_hover"],
            activeforeground=t["accent_fg"],
        )
        self.ask_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.stop_btn = tk.Button(
            row_q, text="Stop", command=self._on_stop, width=10,
            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            font=FONT_BOLD, relief=tk.FLAT, bd=0,
            padx=24, pady=8, state=tk.DISABLED,
            activebackground=t["accent_hover"],
            activeforeground=t["accent_fg"],
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        # -- Top-k selector --
        topk_row = tk.Frame(self, bg=t["panel_bg"])
        topk_row.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            topk_row, text="Top-K:", bg=t["panel_bg"],
            fg=t["fg"], font=FONT,
        ).pack(side=tk.LEFT)

        self._topk_var = tk.IntVar(value=10)
        self._topk_spin = tk.Spinbox(
            topk_row, from_=1, to=50, textvariable=self._topk_var,
            width=5, font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            buttonbackground=t["input_bg"], relief=tk.FLAT, bd=1,
        )
        self._topk_spin.pack(side=tk.LEFT, padx=(8, 0))

        # -- Advanced retrieval controls (expandable) --
        self._adv_visible = False
        self._adv_toggle = tk.Button(
            self, text="+ Advanced", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["gray"], relief=tk.FLAT, bd=0,
            command=self._toggle_advanced, anchor=tk.W, cursor="hand2",
        )
        self._adv_toggle.pack(fill=tk.X, pady=(0, 2))

        self._adv_frame = tk.Frame(self, bg=t["panel_bg"])
        # Not packed yet — shown on toggle

        cfg = model.config if model else None
        retrieval = cfg.retrieval if cfg and hasattr(cfg, "retrieval") else None

        # Candidate Pool
        cp_row = tk.Frame(self._adv_frame, bg=t["panel_bg"])
        cp_row.pack(fill=tk.X, pady=1)
        tk.Label(cp_row, text="Candidate Pool:", bg=t["panel_bg"], fg=t["fg"], font=FONT_SMALL, width=16, anchor=tk.W).pack(side=tk.LEFT)
        self._candidate_pool_var = tk.IntVar(value=retrieval.candidate_pool if retrieval else 30)
        tk.Spinbox(cp_row, from_=10, to=200, textvariable=self._candidate_pool_var, width=5, font=FONT_SMALL, bg=t["input_bg"], fg=t["input_fg"], relief=tk.FLAT, bd=1).pack(side=tk.LEFT, padx=(4, 0))

        # Min Score
        ms_row = tk.Frame(self._adv_frame, bg=t["panel_bg"])
        ms_row.pack(fill=tk.X, pady=1)
        tk.Label(ms_row, text="Min Score:", bg=t["panel_bg"], fg=t["fg"], font=FONT_SMALL, width=16, anchor=tk.W).pack(side=tk.LEFT)
        self._min_score_var = tk.DoubleVar(value=retrieval.min_score if retrieval else 0.0)
        self._min_score_scale = tk.Scale(ms_row, from_=0.0, to=1.0, resolution=0.05, orient=tk.HORIZONTAL, variable=self._min_score_var, length=120, font=FONT_SMALL, bg=t["panel_bg"], fg=t["fg"], troughcolor=t["input_bg"], highlightthickness=0)
        self._min_score_scale.pack(side=tk.LEFT, padx=(4, 0))

        # Reranker Top-N
        rn_row = tk.Frame(self._adv_frame, bg=t["panel_bg"])
        rn_row.pack(fill=tk.X, pady=1)
        tk.Label(rn_row, text="Reranker Top-N:", bg=t["panel_bg"], fg=t["fg"], font=FONT_SMALL, width=16, anchor=tk.W).pack(side=tk.LEFT)
        self._reranker_topn_var = tk.IntVar(value=retrieval.reranker_top_n if retrieval else 5)
        tk.Spinbox(rn_row, from_=1, to=50, textvariable=self._reranker_topn_var, width=5, font=FONT_SMALL, bg=t["input_bg"], fg=t["input_fg"], relief=tk.FLAT, bd=1).pack(side=tk.LEFT, padx=(4, 0))

        # Reranker Toggle
        rt_row = tk.Frame(self._adv_frame, bg=t["panel_bg"])
        rt_row.pack(fill=tk.X, pady=1)
        self._reranker_enabled_var = tk.BooleanVar(value=retrieval.reranker_enabled if retrieval else True)
        tk.Checkbutton(rt_row, text="Reranker Enabled", variable=self._reranker_enabled_var, bg=t["panel_bg"], fg=t["fg"], font=FONT_SMALL, selectcolor=t["input_bg"], activebackground=t["panel_bg"]).pack(side=tk.LEFT)

        # -- Network/status indicator --
        self._status_label = tk.Label(
            self, text="", fg=t["gray"], anchor=tk.W,
            bg=t["panel_bg"], font=FONT, justify=tk.LEFT,
        )
        self._status_label.pack(fill=tk.X)

        # -- Answer area (scrollable, selectable) --
        answer_frame = tk.Frame(self, bg=t["panel_bg"])
        answer_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        scrollbar = tk.Scrollbar(answer_frame, orient=tk.VERTICAL)
        self.answer_text = tk.Text(
            answer_frame, height=16, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT, bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], relief=tk.FLAT, bd=1,
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.answer_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.answer_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # -- Feedback buttons --
        self._feedback_frame = tk.Frame(self, bg=t["panel_bg"])
        self._feedback_frame.pack(fill=tk.X, pady=(8, 0))

        self._feedback_label = tk.Label(
            self._feedback_frame, text="Was this helpful?",
            bg=t["panel_bg"], fg=t["gray"], font=FONT_SMALL,
        )
        self._feedback_label.pack(side=tk.LEFT)

        self._feedback_btns = {}
        for label, value in [
            ("\u2714 Helpful", "helpful"),
            ("\u2718 Not Helpful", "not_helpful"),
            ("\u26A0 Wrong Answer", "wrong_answer"),
            ("\u2757 Bad Sources", "bad_sources"),
        ]:
            btn = tk.Button(
                self._feedback_frame, text=label, font=FONT_SMALL,
                bg=t["panel_bg"], fg=t["fg"], relief=tk.FLAT,
                padx=8, pady=2, cursor="hand2",
                command=lambda v=value: self._on_feedback(v),
                activebackground=t["accent"],
                activeforeground=t["accent_fg"],
            )
            btn.pack(side=tk.LEFT, padx=(6, 0))
            self._feedback_btns[value] = btn

        # Hide feedback until a query completes
        self._feedback_frame.pack_forget()

        # Session log path
        self._session_log_dir = Path("data/query_sessions")
        self._session_log_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: dict | None = None

        # -- Copy/Export buttons --
        self._action_frame = tk.Frame(self, bg=t["panel_bg"])
        self._action_frame.pack(fill=tk.X, pady=(4, 0))

        self._copy_answer_btn = tk.Button(
            self._action_frame, text="Copy Answer", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            padx=8, pady=2, cursor="hand2",
            command=self._copy_answer,
            activebackground=t["accent"],
            activeforeground=t["accent_fg"],
        )
        self._copy_answer_btn.pack(side=tk.LEFT)

        self._copy_sources_btn = tk.Button(
            self._action_frame, text="Copy Sources", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            padx=8, pady=2, cursor="hand2",
            command=self._copy_sources,
            activebackground=t["accent"],
            activeforeground=t["accent_fg"],
        )
        self._copy_sources_btn.pack(side=tk.LEFT, padx=(6, 0))

        self._export_btn = tk.Button(
            self._action_frame, text="Export Session Log", font=FONT_SMALL,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            padx=8, pady=2, cursor="hand2",
            command=self._export_session_log,
            activebackground=t["accent"],
            activeforeground=t["accent_fg"],
        )
        self._export_btn.pack(side=tk.LEFT, padx=(6, 0))

        # Hide action buttons until a query completes
        self._action_frame.pack_forget()

        # -- Sources expandable section --
        self._sources_frame = tk.Frame(self, bg=t["panel_bg"])
        self._sources_frame.pack(fill=tk.X, pady=(8, 0))

        self._sources_toggle_btn = tk.Button(
            self._sources_frame, text="+ Sources (0)", font=FONT,
            bg=t["panel_bg"], fg=t["accent"], relief=tk.FLAT,
            command=self._toggle_sources, cursor="hand2",
            activebackground=t["panel_bg"], activeforeground=t["accent_hover"],
        )
        self._sources_toggle_btn.pack(anchor=tk.W)

        self._sources_detail = tk.Text(
            self._sources_frame, height=4, wrap=tk.WORD, state=tk.DISABLED,
            font=FONT_SMALL, bg=t["input_bg"], fg=t["input_fg"],
            relief=tk.FLAT, bd=1,
        )
        self._sources_expanded = False

        # -- Metrics line --
        self._metrics_label = tk.Label(
            self, text="", anchor=tk.W, fg=t["gray"],
            bg=t["panel_bg"], font=FONT_MONO, justify=tk.LEFT,
        )
        self._metrics_label.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Placeholder handling
    # ------------------------------------------------------------------

    def _on_entry_focus(self, event=None):
        """Clear placeholder text on first focus."""
        if self.question_entry.get() == "Type your question here...":
            self.question_entry.delete(0, tk.END)

    def _toggle_advanced(self):
        """Show/hide the Advanced retrieval controls drawer."""
        if self._adv_visible:
            self._adv_frame.pack_forget()
            self._adv_toggle.config(text="+ Advanced")
            self._adv_visible = False
        else:
            self._adv_frame.pack(fill=tk.X, pady=(0, 4), before=self._status_label)
            self._adv_toggle.config(text="- Advanced")
            self._adv_visible = True

    def _get_advanced_config(self):
        """Read current advanced control values for the next query."""
        return {
            "candidate_pool": self._candidate_pool_var.get(),
            "min_score": self._min_score_var.get(),
            "reranker_top_n": self._reranker_topn_var.get(),
            "reranker_enabled": self._reranker_enabled_var.get(),
        }

    # ------------------------------------------------------------------
    # Ready check
    # ------------------------------------------------------------------

    def _check_ready(self):
        """Enable Ask button once the model pipeline is available."""
        t = current_theme()
        if self._model and self._model.pipeline is not None:
            self.ask_btn.config(
                state=tk.NORMAL,
                bg=t["accent"], fg=t["accent_fg"],
            )
        else:
            # Retry in 500ms
            self.after(500, self._check_ready)

    def set_ready(self, ready: bool):
        """Externally signal readiness (called after backend init)."""
        t = current_theme()
        if ready:
            self.ask_btn.config(
                state=tk.NORMAL,
                bg=t["accent"], fg=t["accent_fg"],
            )
        else:
            self.ask_btn.config(
                state=tk.DISABLED,
                bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            )

    # ------------------------------------------------------------------
    # Query lifecycle
    # ------------------------------------------------------------------

    def _on_ask(self, event=None):
        """Handle Ask button click or Enter key."""
        question = self.question_entry.get().strip()
        if not question or question == "Type your question here...":
            return
        if self._model is None or self._model.is_querying:
            return

        t = current_theme()
        top_k = self._topk_var.get()

        # Clear previous answer
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.config(state=tk.DISABLED)

        # Reset badges
        self._path_badge.config(text="", fg=t["gray"])
        self._confidence_badge.config(text="", fg=t["gray"])
        self._evidence_badge.config(text="", fg=t["gray"], bg=t["panel_bg"])

        # Update UI state
        self.ask_btn.config(state=tk.DISABLED,
                            bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"])
        self.stop_btn.config(state=tk.NORMAL,
                             bg=t["red"], fg=t["accent_fg"])
        self._status_label.config(text="Classifying query...", fg=t["orange"])

        # Start elapsed timer
        self._stream_start = time.time()
        self._update_elapsed()

        # Show phased status — classifying first, then update during query
        def _phase_update():
            elapsed = time.time() - self._stream_start
            if self._model and self._model.is_querying:
                if elapsed < 2:
                    self._status_label.config(text="Classifying query...", fg=t["orange"])
                elif elapsed < 5:
                    self._status_label.config(text="Searching 10.4M documents...", fg=t["orange"])
                else:
                    self._status_label.config(
                        text="Generating answer... ({:.0f}s)".format(elapsed),
                        fg=t["orange"],
                    )
                self.after(500, _phase_update)
        self.after(500, _phase_update)

        # Dispatch via model
        self._model.query(
            text=question,
            top_k=top_k,
            callback=lambda resp: safe_after(self, 0, self._on_query_done, resp),
            error_callback=lambda exc: safe_after(self, 0, self._on_query_error, exc),
        )

    def _on_stop(self, event=None):
        """Handle Stop button click or Escape key."""
        if self._model:
            self._model.cancel_query()
        self._finish_query_ui()
        t = current_theme()
        self._status_label.config(text="Query cancelled.", fg=t["orange"])

    def _on_query_done(self, response):
        """Handle successful query response (runs on main thread via safe_after)."""
        t = current_theme()

        # Set query path badge
        path = getattr(response, "query_path", "SEMANTIC")
        path_color_key = _PATH_COLORS.get(path, "fg")
        self._path_badge.config(
            text=" {} ".format(path),
            fg=t["accent_fg"],
            bg=t.get(path_color_key, t["accent"]),
        )

        # Set confidence badge
        confidence = getattr(response, "confidence", "")
        conf_color_key = _CONFIDENCE_COLORS.get(confidence, "gray")
        self._confidence_badge.config(
            text=" {} ".format(confidence),
            fg=t["accent_fg"],
            bg=t.get(conf_color_key, t["gray"]),
        )

        # Display answer with empty/weak-evidence handling
        answer = getattr(response, "answer", "") or ""
        if not answer.strip() or answer.strip() == "[NOT_FOUND]":
            answer = (
                "No relevant documents found for this query.\n\n"
                "Try:\n"
                "  - Rephrasing with more specific terms\n"
                "  - Including a CDRL code (e.g., A009), site name, or date\n"
                "  - Checking the Entities tab for available data"
            )
        elif confidence == "NOT_FOUND":
            answer = (
                "The search found some documents but confidence is low.\n\n"
                + answer + "\n\n"
                "Note: This answer may be incomplete. Consider refining your query "
                "with more specific terms."
            )
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", answer)
        self.answer_text.config(state=tk.DISABLED)

        # Set evidence basis badge
        question = self.question_entry.get().strip()
        evidence_type = _classify_evidence_basis(question, answer, path)
        ev_label, ev_color_key = _EVIDENCE_LABELS.get(evidence_type, ("", "gray"))
        self._evidence_badge.config(
            text=" {} ".format(ev_label),
            fg=t["accent_fg"],
            bg=t.get(ev_color_key, t["gray"]),
        )

        # Update sources
        sources = getattr(response, "sources", []) or []
        self._update_sources(sources)

        # Metrics line
        latency = getattr(response, "latency_ms", 0)
        chunks = getattr(response, "chunks_used", 0)
        in_tok = getattr(response, "input_tokens", 0)
        out_tok = getattr(response, "output_tokens", 0)
        metrics_parts = [
            "Latency: {}ms".format(latency),
            "Chunks: {}".format(chunks),
        ]
        if in_tok or out_tok:
            metrics_parts.append("Tokens: {}in/{}out".format(in_tok, out_tok))
        self._metrics_label.config(text="  |  ".join(metrics_parts), fg=t["fg"])

        # Update status bar query path
        self._notify_status_bar(path)

        # Log session and show feedback/action buttons
        question = self.question_entry.get().strip()
        self._current_session = self._log_session(question, response)
        self._feedback_frame.pack(fill=tk.X, pady=(8, 0))
        self._action_frame.pack(fill=tk.X, pady=(4, 0))
        # Reset feedback button colors
        for btn in self._feedback_btns.values():
            btn.config(bg=t["panel_bg"], fg=t["fg"])

        self._finish_query_ui()
        elapsed = time.time() - self._stream_start if hasattr(self, "_stream_start") else 0
        chunks = getattr(response, "chunks_used", 0)
        self._status_label.config(
            text="Done ({:.1f}s) — {} chunks retrieved".format(elapsed, chunks),
            fg=t["green"],
        )

    def _on_query_error(self, exc):
        """Handle query error with operator-friendly messages."""
        t = current_theme()
        exc_str = str(exc).lower()

        # Classify the error for operator-friendly messaging
        if "timeout" in exc_str or "timed out" in exc_str:
            title = "Query Timed Out"
            message = (
                "The search took too long and was stopped.\n\n"
                "Try:\n"
                "  - Simplifying your question\n"
                "  - Reducing Top-K to 5\n"
                "  - Asking about a specific document or site"
            )
            badge_text = " TIMEOUT "
        elif "connection" in exc_str or "connect" in exc_str or "refused" in exc_str:
            title = "Service Unavailable"
            message = (
                "Could not connect to the search backend.\n\n"
                "Check that:\n"
                "  - The LLM service is running\n"
                "  - Network connection is available\n"
                "  - Try again in a moment"
            )
            badge_text = " OFFLINE "
        elif "api" in exc_str or "rate" in exc_str or "quota" in exc_str:
            title = "API Error"
            message = (
                "The language model service returned an error.\n\n"
                "This may be a temporary issue. Try again in a moment.\n"
                "If it persists, check API key configuration in Settings."
            )
            badge_text = " API ERROR "
        else:
            title = "Query Failed"
            message = "An unexpected error occurred:\n\n{}".format(str(exc))
            badge_text = " ERROR "

        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", message)
        self.answer_text.config(state=tk.DISABLED)

        self._confidence_badge.config(
            text=badge_text, fg=t["accent_fg"], bg=t["red"],
        )
        self._finish_query_ui()
        self._status_label.config(text=title, fg=t["red"])

    def _finish_query_ui(self):
        """Restore UI to idle state after query completes or cancels."""
        t = current_theme()
        ready = self._model and self._model.pipeline is not None
        if ready:
            self.ask_btn.config(
                state=tk.NORMAL, bg=t["accent"], fg=t["accent_fg"],
            )
        else:
            self.ask_btn.config(
                state=tk.DISABLED, bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
            )
        self.stop_btn.config(
            state=tk.DISABLED, bg=t["inactive_btn_bg"], fg=t["inactive_btn_fg"],
        )

        # Stop elapsed timer
        if self._elapsed_timer_id is not None:
            try:
                self.after_cancel(self._elapsed_timer_id)
            except Exception:
                pass
            self._elapsed_timer_id = None

    # ------------------------------------------------------------------
    # Elapsed timer
    # ------------------------------------------------------------------

    def _update_elapsed(self):
        """Update elapsed time display every 100ms during a query."""
        t = current_theme()
        if self._model and self._model.is_querying:
            elapsed = time.time() - self._stream_start
            self._elapsed_label.config(text="{:.1f}s".format(elapsed))
            # Slow query warning at 30s
            if elapsed > 30 and elapsed < 31:
                self._status_label.config(
                    text="Still searching... complex queries may take up to 60s.",
                    fg=t["orange"],
                )
            elif elapsed > 60 and elapsed < 61:
                self._status_label.config(
                    text="This query is taking longer than usual. You can press Stop to cancel.",
                    fg=t["red"],
                )
            self._elapsed_timer_id = self.after(100, self._update_elapsed)
        else:
            elapsed = time.time() - self._stream_start
            self._elapsed_label.config(text="{:.1f}s".format(elapsed))

    # ------------------------------------------------------------------
    # Sources expandable section
    # ------------------------------------------------------------------

    def _update_sources(self, sources):
        """Update the sources expandable section."""
        count = len(sources)
        prefix = "-" if self._sources_expanded else "+"
        self._sources_toggle_btn.config(
            text="{} Sources ({})".format(prefix, count)
        )
        self._sources_detail.config(state=tk.NORMAL)
        self._sources_detail.delete("1.0", tk.END)
        if sources:
            self._sources_detail.insert("1.0", "\n".join(sources))
        else:
            self._sources_detail.insert("1.0", "(no sources)")
        self._sources_detail.config(state=tk.DISABLED)

    def _toggle_sources(self):
        """Toggle the sources detail section visibility."""
        if self._sources_expanded:
            self._sources_detail.pack_forget()
            self._sources_expanded = False
            text = self._sources_toggle_btn.cget("text")
            self._sources_toggle_btn.config(text=text.replace("-", "+", 1))
        else:
            self._sources_detail.pack(fill=tk.X, pady=(4, 0))
            self._sources_expanded = True
            text = self._sources_toggle_btn.cget("text")
            self._sources_toggle_btn.config(text=text.replace("+", "-", 1))

    # ------------------------------------------------------------------
    # Status bar integration
    # ------------------------------------------------------------------

    def _notify_status_bar(self, path_name):
        """Push query path to the status bar if accessible."""
        try:
            widget = self.master
            while widget is not None:
                if hasattr(widget, "status_bar"):
                    widget.status_bar.set_query_path(path_name)
                    break
                widget = getattr(widget, "master", None)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Feedback + Session logging
    # ------------------------------------------------------------------

    def _on_feedback(self, feedback_value: str):
        """Record operator feedback for the current query session."""
        t = current_theme()
        if self._current_session:
            self._current_session["feedback"] = feedback_value
            self._current_session["feedback_at"] = datetime.now().isoformat()
            self._save_session(self._current_session)
        # Visual confirmation
        for value, btn in self._feedback_btns.items():
            if value == feedback_value:
                btn.config(bg=t["accent"], fg=t["accent_fg"])
            else:
                btn.config(bg=t["panel_bg"], fg=t["gray"])

    def _log_session(self, question: str, response) -> dict:
        """Create a session record for persistence."""
        session = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": getattr(response, "answer", ""),
            "query_path": getattr(response, "query_path", ""),
            "confidence": getattr(response, "confidence", ""),
            "sources": getattr(response, "sources", []) or [],
            "latency_ms": getattr(response, "latency_ms", 0),
            "chunks_used": getattr(response, "chunks_used", 0),
            "feedback": None,
            "feedback_at": None,
        }
        self._save_session(session)
        return session

    def _save_session(self, session: dict):
        """Append session to the daily log file."""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_file = self._session_log_dir / f"sessions_{date_str}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(session, default=str) + "\n")
        except Exception as e:
            logger.warning("Failed to save session log: %s", e)

    def _copy_answer(self):
        """Copy the current answer text to clipboard."""
        try:
            text = self.answer_text.get("1.0", tk.END).strip()
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                t = current_theme()
                self._copy_answer_btn.config(text="Copied!", fg=t["green"])
                self.after(2000, lambda: self._copy_answer_btn.config(
                    text="Copy Answer", fg=t["accent"]))
        except Exception:
            pass

    def _copy_sources(self):
        """Copy the sources list to clipboard."""
        try:
            text = self._sources_detail.get("1.0", tk.END).strip()
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                t = current_theme()
                self._copy_sources_btn.config(text="Copied!", fg=t["green"])
                self.after(2000, lambda: self._copy_sources_btn.config(
                    text="Copy Sources", fg=t["accent"]))
        except Exception:
            pass

    def _export_session_log(self):
        """Open a file dialog to export the session log."""
        try:
            from tkinter import filedialog
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_file = self._session_log_dir / f"sessions_{date_str}.jsonl"
            if not log_file.exists():
                return
            dest = filedialog.asksaveasfilename(
                defaultextension=".jsonl",
                filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")],
                initialfile=f"query_sessions_{date_str}.jsonl",
            )
            if dest:
                import shutil
                shutil.copy2(str(log_file), dest)
                t = current_theme()
                self._export_btn.config(text="Exported!", fg=t["green"])
                self.after(2000, lambda: self._export_btn.config(
                    text="Export Session Log", fg=t["accent"]))
        except Exception as e:
            logger.warning("Failed to export session log: %s", e)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_theme(self, t):
        """Re-apply theme colors to all widgets."""
        self.configure(bg=t["panel_bg"], fg=t["accent"])

        for child in self.winfo_children():
            if isinstance(child, tk.Frame):
                try:
                    child.configure(bg=t["panel_bg"])
                except Exception:
                    pass

        self.question_entry.configure(
            bg=t["input_bg"], fg=t["input_fg"], insertbackground=t["fg"],
        )
        self.answer_text.configure(
            bg=t["input_bg"], fg=t["input_fg"],
            insertbackground=t["fg"], selectbackground=t["accent"],
        )
        self._status_label.configure(bg=t["panel_bg"])
        self._metrics_label.configure(bg=t["panel_bg"])
        self._elapsed_label.configure(bg=t["panel_bg"])
        self._sources_toggle_btn.configure(bg=t["panel_bg"], fg=t["accent"])
        self._sources_detail.configure(bg=t["input_bg"], fg=t["input_fg"])
